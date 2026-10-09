"""Steam game recording clips -> regular MP4 files.

Steam saves each clip as MPEG-DASH segments:

    <userdata>/<id>/gamerecordings/clips/clip_<appid>_<YYYYMMDD>_<HHMMSS>/
        clip.pb, thumbnail.jpg, timelines/, video/<fg|bg>_<appid>_<date>_<time>/
            session.mpd, init-stream0.m4s, init-stream1.m4s,
            chunk-stream0-00001.m4s, chunk-stream1-00001.m4s, ...

Steam only shares clips up to 59 seconds to a phone and exports MP4 only in
Desktop Mode. This module rebuilds the segments into one ordinary
(non-fragmented, "fast start") MP4 without re-encoding, in pure Python, so any
phone can play and save it. Video and audio samples are copied byte for byte.
"""
from __future__ import annotations

import os
import re
import struct
import threading
import time
from pathlib import Path

CLIP_DIR_RE = re.compile(r"^clip_(\d+)_(\d{8})_(\d{6})$")
CHUNK_RE = re.compile(r"^chunk-stream(\d+)-(\d+)\.m4s$")
MOVIE_TIMESCALE = 1000
COPY_BLOCK = 4 * 1024 * 1024


class ClipError(Exception):
    pass


# --------------------------------------------------------------------------
# ISO BMFF box helpers


def iter_boxes(data, start=0, end=None):
    """Yield (type, box_start, payload_start, box_end) for boxes in data[start:end]."""
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, btype = struct.unpack_from(">I4s", data, pos)
        header = 8
        if size == 1:
            if pos + 16 > end:
                break
            size = struct.unpack_from(">Q", data, pos + 8)[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            break
        yield btype.decode("latin-1"), pos, pos + header, pos + size
        pos += size


def find_box(data, path, start=0, end=None):
    """Return (payload_start, box_end) of the first box at a '/'-separated path."""
    parts = path.split("/")
    for btype, _, pstart, bend in iter_boxes(data, start, end):
        if btype == parts[0]:
            if len(parts) == 1:
                return pstart, bend
            return find_box(data, "/".join(parts[1:]), pstart, bend)
    return None


def box(btype, payload):
    size = 8 + len(payload)
    if size > 0xFFFFFFFF:
        return struct.pack(">I4sQ", 1, btype.encode(), size + 8) + payload
    return struct.pack(">I4s", size, btype.encode()) + payload


def full_box(btype, version, flags, payload):
    return box(btype, struct.pack(">I", (version << 24) | flags) + payload)


def iter_top_level_boxes_in_file(fh, file_size):
    """Yield (type, box_start, payload_start, box_end) for top-level boxes of a file."""
    pos = 0
    while pos + 8 <= file_size:
        fh.seek(pos)
        head = fh.read(16)
        if len(head) < 8:
            break
        size, btype = struct.unpack_from(">I4s", head, 0)
        header = 8
        if size == 1:
            size = struct.unpack_from(">Q", head, 8)[0]
            header = 16
        elif size == 0:
            size = file_size - pos
        if size < header or pos + size > file_size:
            break
        yield btype.decode("latin-1"), pos, pos + header, pos + size
        pos += size


# --------------------------------------------------------------------------
# Init segment (one track)


class InitTrack:
    def __init__(self, path: Path):
        self.path = path
        data = path.read_bytes()
        self.data = data
        moov = find_box(data, "moov")
        if not moov:
            raise ClipError(f"{path.name}: no moov box")
        trak = find_box(data, "trak", *moov)
        if not trak:
            raise ClipError(f"{path.name}: no track")
        self.trak = trak
        tkhd = find_box(data, "tkhd", *trak)
        version = data[tkhd[0]]
        self.track_id = struct.unpack_from(">I", data, tkhd[0] + (20 if version == 1 else 12))[0]
        mdhd = find_box(data, "mdia/mdhd", *trak)
        version = data[mdhd[0]]
        self.timescale = struct.unpack_from(">I", data, mdhd[0] + (20 if version == 1 else 12))[0]
        hdlr = find_box(data, "mdia/hdlr", *trak)
        self.handler = data[hdlr[0] + 8:hdlr[0] + 12].decode("latin-1")
        stsd = find_box(data, "mdia/minf/stbl/stsd", *trak)
        self.stsd_payload = data[stsd[0]:stsd[1]]
        # Presentation offset the encoder declared (B-frame delay / AAC priming).
        self.edit_media_time = 0
        elst = find_box(data, "edts/elst", *trak)
        if elst:
            version = data[elst[0]]
            count = struct.unpack_from(">I", data, elst[0] + 4)[0]
            pos = elst[0] + 8
            for _ in range(count):
                if version == 1:
                    _, media_time = struct.unpack_from(">Qq", data, pos)
                    pos += 20
                else:
                    _, media_time = struct.unpack_from(">Ii", data, pos)
                    pos += 12
                if media_time >= 0:
                    self.edit_media_time = media_time
                    break
        self.trex = {}
        mvex = find_box(data, "mvex", *moov)
        if mvex:
            for btype, _, p, e in iter_boxes(data, *mvex):
                if btype == "trex":
                    tid, sdi, dur, size, flags = struct.unpack_from(">IIIII", data, p + 4)
                    self.trex = {"track_id": tid, "duration": dur, "size": size, "flags": flags}
        self.width = self.height = 0
        if self.handler == "vide":
            v = data[tkhd[0]]
            off = tkhd[0] + (4 + 8 + 8 + 4 + 4 + 8 + 8 + 2 + 2 + 2 + 2 + 36 if v == 1 else 4 + 4 + 4 + 4 + 4 + 4 + 8 + 2 + 2 + 2 + 2 + 36)
            self.width = struct.unpack_from(">I", data, off)[0] >> 16
            self.height = struct.unpack_from(">I", data, off + 4)[0] >> 16

    def rebuild_trak(self, track_id, media_duration, edits, tables):
        """Copy this track's trak box with new ids, durations, edit list and sample tables."""
        data = self.data

        def rebuild(start, end, path):
            out = bytearray()
            for btype, bstart, pstart, bend in iter_boxes(data, start, end):
                here = f"{path}/{btype}" if path else btype
                if btype == "tkhd":
                    out += _patch_tkhd(data[pstart:bend], track_id, edits_duration(edits))
                elif btype == "edts":
                    continue
                elif btype == "mdhd":
                    out += box("mdhd", _patch_mdhd(data[pstart:bend], media_duration))
                elif btype == "stbl":
                    out += box("stbl", box("stsd", self.stsd_payload) + tables)
                elif btype in ("mdia", "minf"):
                    out += box(btype, rebuild(pstart, bend, here))
                else:
                    out += data[bstart:bend]
                if btype == "tkhd" and edits:
                    out += box("edts", _elst(edits))
            return bytes(out)

        return box("trak", rebuild(self.trak[0], self.trak[1], ""))


def edits_duration(edits):
    return sum(e[0] for e in edits) if edits else None


def _patch_tkhd(payload, track_id, duration):
    p = bytearray(payload)
    version = p[0]
    p[1:4] = b"\x00\x00\x07"  # enabled | in movie | in preview
    if version == 1:
        struct.pack_into(">I", p, 20, track_id)
        if duration is not None:
            struct.pack_into(">Q", p, 28, duration)
    else:
        struct.pack_into(">I", p, 12, track_id)
        if duration is not None:
            struct.pack_into(">I", p, 20, min(duration, 0xFFFFFFFF))
    return box("tkhd", bytes(p))


def _patch_mdhd(payload, duration):
    p = bytearray(payload)
    if p[0] == 1:
        struct.pack_into(">Q", p, 24, duration)
    elif duration > 0xFFFFFFFF:
        # Switch to version 1 for very long media.
        ctime, mtime, ts, _ = struct.unpack_from(">IIII", p, 4)
        rest = bytes(p[20:])
        return struct.pack(">I", 1 << 24) + struct.pack(">QQIQ", ctime, mtime, ts, duration) + rest
    else:
        struct.pack_into(">I", p, 16, duration)
    return bytes(p)


def _elst(edits):
    """edits: list of (segment_duration_movie_ts, media_time) ; media_time -1 = empty edit."""
    big = any(d > 0xFFFFFFFF or abs(m) > 0x7FFFFFFF for d, m in edits)
    if big:
        body = struct.pack(">I", len(edits)) + b"".join(struct.pack(">QqHH", d, m, 1, 0) for d, m in edits)
        return full_box("elst", 1, 0, body)
    body = struct.pack(">I", len(edits)) + b"".join(struct.pack(">IiHH", d, m, 1, 0) for d, m in edits)
    return full_box("elst", 0, 0, body)


# --------------------------------------------------------------------------
# Media segments


class TrackSamples:
    """Sample tables collected from all fragments of one track."""

    def __init__(self, init: InitTrack):
        self.init = init
        self.durations = []
        self.sizes = []
        self.non_sync = []  # indexes (0-based) of non-sync samples
        self.cto = []
        self.has_cto = False
        self.negative_cto = False
        self.runs = []  # (file_path, offset, byte_length, first_sample_index, sample_count, start_dts)
        self.first_dts = None
        self.next_dts = None

    @property
    def count(self):
        return len(self.sizes)

    @property
    def media_duration(self):
        return sum(self.durations)

    def add_segment(self, path: Path):
        size = path.stat().st_size
        with open(path, "rb") as fh:
            for btype, bstart, pstart, bend in iter_top_level_boxes_in_file(fh, size):
                if btype != "moof":
                    continue
                fh.seek(bstart)
                moof = fh.read(bend - bstart)
                self._add_moof(path, moof, bstart)

    def _add_moof(self, path, moof, moof_offset):
        for btype, _, tp, te in iter_boxes(moof, 8):
            if btype != "traf":
                continue
            tfhd = find_box(moof, "tfhd", tp, te)
            if not tfhd:
                continue
            flags = struct.unpack_from(">I", moof, tfhd[0])[0] & 0xFFFFFF
            pos = tfhd[0] + 8
            base = None
            d_dur = self.init.trex.get("duration", 0)
            d_size = self.init.trex.get("size", 0)
            d_flags = self.init.trex.get("flags", 0)
            if flags & 0x1:
                base = struct.unpack_from(">Q", moof, pos)[0]
                pos += 8
            if flags & 0x2:
                pos += 4
            if flags & 0x8:
                d_dur = struct.unpack_from(">I", moof, pos)[0]
                pos += 4
            if flags & 0x10:
                d_size = struct.unpack_from(">I", moof, pos)[0]
                pos += 4
            if flags & 0x20:
                d_flags = struct.unpack_from(">I", moof, pos)[0]
                pos += 4
            if base is None:
                base = moof_offset  # default-base-is-moof (and the single-traf default)
            tfdt = find_box(moof, "tfdt", tp, te)
            dts = None
            if tfdt:
                if moof[tfdt[0]] == 1:
                    dts = struct.unpack_from(">Q", moof, tfdt[0] + 4)[0]
                else:
                    dts = struct.unpack_from(">I", moof, tfdt[0] + 4)[0]
            if dts is None:
                dts = self.next_dts or 0
            if self.first_dts is None:
                self.first_dts = dts
            elif self.next_dts is not None and dts > self.next_dts:
                # Gap in the recording: stretch the previous sample to keep A/V in sync.
                if self.durations:
                    self.durations[-1] += dts - self.next_dts
            next_offset = base
            for rtype, _, rp, re_ in iter_boxes(moof, tp, te):
                if rtype != "trun":
                    continue
                version = moof[rp]
                rflags = struct.unpack_from(">I", moof, rp)[0] & 0xFFFFFF
                count = struct.unpack_from(">I", moof, rp + 4)[0]
                q = rp + 8
                offset = next_offset
                if rflags & 0x1:
                    offset = base + struct.unpack_from(">i", moof, q)[0]
                    q += 4
                first_flags = None
                if rflags & 0x4:
                    first_flags = struct.unpack_from(">I", moof, q)[0]
                    q += 4
                first_index = self.count
                run_bytes = 0
                run_dts = dts
                for i in range(count):
                    dur, sz, fl, cto = d_dur, d_size, d_flags, 0
                    if rflags & 0x100:
                        dur = struct.unpack_from(">I", moof, q)[0]
                        q += 4
                    if rflags & 0x200:
                        sz = struct.unpack_from(">I", moof, q)[0]
                        q += 4
                    if rflags & 0x400:
                        fl = struct.unpack_from(">I", moof, q)[0]
                        q += 4
                    elif i == 0 and first_flags is not None:
                        fl = first_flags
                    if rflags & 0x800:
                        cto = struct.unpack_from(">i" if version else ">I", moof, q)[0]
                        q += 4
                    self.durations.append(dur)
                    self.sizes.append(sz)
                    self.cto.append(cto)
                    if cto:
                        self.has_cto = True
                        if cto < 0:
                            self.negative_cto = True
                    if fl & 0x10000:
                        self.non_sync.append(self.count - 1)
                    run_bytes += sz
                    dts += dur
                if count:
                    self.runs.append((path, offset, run_bytes, first_index, count, run_dts))
                next_offset = offset + run_bytes
            self.next_dts = dts

    def presentation_delay(self):
        """Smallest composition offset relative to decode time (B-frame delay)."""
        if not self.has_cto:
            return 0
        best = None
        t = 0
        for dur, cto in zip(self.durations, self.cto):
            pts = t + cto
            best = pts if best is None or pts < best else best
            t += dur
        return max(0, best or 0)

    def tables(self, chunk_offsets, use_co64):
        out = bytearray()
        # stts
        entries = []
        for d in self.durations:
            if entries and entries[-1][1] == d:
                entries[-1][0] += 1
            else:
                entries.append([1, d])
        out += full_box("stts", 0, 0, struct.pack(">I", len(entries)) + b"".join(struct.pack(">II", c, d) for c, d in entries))
        # ctts
        if self.has_cto:
            entries = []
            for c in self.cto:
                if entries and entries[-1][1] == c:
                    entries[-1][0] += 1
                else:
                    entries.append([1, c])
            fmt = ">Ii" if self.negative_cto else ">II"
            out += full_box("ctts", 1 if self.negative_cto else 0, 0,
                            struct.pack(">I", len(entries)) + b"".join(struct.pack(fmt, c, o) for c, o in entries))
        # stss (absent = every sample is a sync sample)
        if self.non_sync:
            ns = set(self.non_sync)
            sync = [i + 1 for i in range(self.count) if i not in ns]
            out += full_box("stss", 0, 0, struct.pack(">I", len(sync)) + b"".join(struct.pack(">I", s) for s in sync))
        # stsc: one chunk per fragment run
        entries = []
        for idx, run in enumerate(self.runs, start=1):
            if not entries or entries[-1][1] != run[4]:
                entries.append((idx, run[4]))
        out += full_box("stsc", 0, 0, struct.pack(">I", len(entries)) + b"".join(struct.pack(">III", f, n, 1) for f, n in entries))
        # stsz
        if self.sizes and all(s == self.sizes[0] for s in self.sizes):
            out += full_box("stsz", 0, 0, struct.pack(">II", self.sizes[0], self.count))
        else:
            out += full_box("stsz", 0, 0, struct.pack(">II", 0, self.count) + struct.pack(f">{self.count}I", *self.sizes))
        # stco / co64
        if use_co64:
            out += full_box("co64", 0, 0, struct.pack(">I", len(chunk_offsets)) + struct.pack(f">{len(chunk_offsets)}Q", *chunk_offsets))
        else:
            out += full_box("stco", 0, 0, struct.pack(">I", len(chunk_offsets)) + struct.pack(f">{len(chunk_offsets)}I", *chunk_offsets))
        return bytes(out)


# --------------------------------------------------------------------------
# Clip discovery


def _chunk_files(video_dir: Path):
    streams = {}
    for f in video_dir.iterdir():
        m = CHUNK_RE.match(f.name)
        if m:
            streams.setdefault(int(m.group(1)), []).append((int(m.group(2)), f))
    return {k: [f for _, f in sorted(v)] for k, v in streams.items()}


def _video_dirs(clip_dir: Path):
    base = clip_dir / "video"
    if not base.is_dir():
        return []
    dirs = [d for d in base.iterdir() if d.is_dir() and (d / "init-stream0.m4s").is_file()]
    return sorted(dirs, key=lambda d: d.name)


_MPD_DURATION = re.compile(r'mediaPresentationDuration="PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?"')


def _mpd_seconds(video_dir: Path):
    try:
        text = (video_dir / "session.mpd").read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return None
    m = _MPD_DURATION.search(text)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)


_SECONDS_CACHE = {}


def _video_seconds(video_dir: Path):
    """Exact video length from the segments themselves (cached)."""
    try:
        files = _chunk_files(video_dir).get(0) or []
        if not files:
            return None
        key = (str(video_dir), len(files), files[-1].stat().st_mtime)
        if key in _SECONDS_CACHE:
            return _SECONDS_CACHE[key]
        track = TrackSamples(InitTrack(video_dir / "init-stream0.m4s"))
        for f in files:
            track.add_segment(f)
        value = round(track.media_duration / track.init.timescale, 1) if track.count else None
        if len(_SECONDS_CACHE) > 500:
            _SECONDS_CACHE.clear()
        _SECONDS_CACHE[key] = value
        return value
    except (OSError, ClipError, struct.error, ValueError):
        return None


def recordings_roots(user_home: Path):
    """Folders that can contain a 'gamerecordings' directory."""
    home = Path(user_home)
    roots = []
    for steam in (home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root"):
        userdata = steam / "userdata"
        if userdata.is_dir():
            for uid in userdata.iterdir():
                if (uid / "gamerecordings").is_dir():
                    roots.append(uid / "gamerecordings")
    # Custom recording folders (for example on the microSD card).
    for media in (Path("/run/media"),):
        if not media.is_dir():
            continue
        try:
            for a in media.iterdir():
                for b in [a] + ([x for x in a.iterdir() if x.is_dir()] if a.is_dir() else []):
                    for c in [b] + ([x for x in b.iterdir() if x.is_dir()] if b.is_dir() else []):
                        if c.name == "gamerecordings" or (c / "clips").is_dir() and c.name.lower().endswith("recordings"):
                            roots.append(c)
                        elif (c / "gamerecordings").is_dir():
                            roots.append(c / "gamerecordings")
        except OSError:
            pass
    seen, unique = set(), []
    for r in roots:
        try:
            key = r.resolve()
        except OSError:
            continue
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def list_clips(user_home: Path, limit=200):
    clips = []
    for root in recordings_roots(user_home):
        clips_dir = root / "clips"
        if not clips_dir.is_dir():
            continue
        for d in clips_dir.iterdir():
            m = CLIP_DIR_RE.match(d.name)
            if not m or not d.is_dir():
                continue
            vdirs = _video_dirs(d)
            if not vdirs:
                continue
            size = 0
            seconds = 0.0
            known = True
            for v in vdirs:
                for f in v.iterdir():
                    if f.name.endswith(".m4s"):
                        try:
                            size += f.stat().st_size
                        except OSError:
                            pass
                s = _video_seconds(v)
                if s is None:
                    s = _mpd_seconds(v)
                if s is None:
                    known = False
                else:
                    seconds += s
            appid, day, clock = m.groups()
            try:
                created = time.mktime(time.strptime(day + clock, "%Y%m%d%H%M%S"))
            except ValueError:
                created = d.stat().st_mtime
            clips.append({
                "id": str(d),
                "appid": appid,
                "created": created,
                "seconds": round(seconds, 1) if known else None,
                "size": size,
                "has_thumbnail": (d / "thumbnail.jpg").is_file(),
            })
    clips.sort(key=lambda c: c["created"], reverse=True)
    return clips[:limit]


def is_clip_dir(path: Path, user_home: Path):
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    if not CLIP_DIR_RE.match(p.name) or not p.is_dir():
        return False
    for root in recordings_roots(user_home):
        try:
            p.relative_to((root / "clips").resolve())
            return True
        except (ValueError, OSError):
            pass
    return False


# --------------------------------------------------------------------------
# Remux


def _load_tracks(clip_dir: Path):
    vdirs = _video_dirs(clip_dir)
    if not vdirs:
        raise ClipError("This clip has no video segments")
    tracks = None
    first_inits = None
    for v in vdirs:
        chunks = _chunk_files(v)
        inits = {}
        for sid in sorted(chunks):
            init_path = v / f"init-stream{sid}.m4s"
            if init_path.is_file():
                inits[sid] = InitTrack(init_path)
        if not inits:
            continue
        if tracks is None:
            first_inits = inits
            tracks = {sid: TrackSamples(init) for sid, init in inits.items()}
        elif set(inits) != set(first_inits) or any(inits[s].stsd_payload != first_inits[s].stsd_payload for s in inits):
            # A later recording session with different settings; keep the first one.
            break
        for sid, files in chunks.items():
            if sid not in tracks:
                continue
            for f in files:
                tracks[sid].add_segment(f)
    if not tracks:
        raise ClipError("This clip has no readable streams")
    tracks = {sid: t for sid, t in tracks.items() if t.count and t.init.handler in ("vide", "soun")}
    if not any(t.init.handler == "vide" for t in tracks.values()):
        raise ClipError("This clip has no video stream")
    return [tracks[s] for s in sorted(tracks)]


def _to_movie(value, timescale):
    return int(round(value * MOVIE_TIMESCALE / timescale))


def _build_moov(tracks, offsets_by_track, use_co64):
    def start_of(t):
        # Original presentation time of the first presented sample, in seconds.
        return (t.first_dts + t.presentation_delay() - t.init.edit_media_time) / t.init.timescale

    video = next(t for t in tracks if t.init.handler == "vide")
    v_start = start_of(video)
    traks = []
    movie_duration = 0
    for new_id, t in enumerate(tracks, start=1):
        ts = t.init.timescale
        delay = t.presentation_delay()
        start = start_of(t)
        media_dur = t.media_duration
        play = media_dur - delay
        edits = []
        if start > v_start + 0.001:
            edits.append((_to_movie((start - v_start) * ts, ts), -1))
            edits.append((_to_movie(play, ts), delay))
        else:
            skip = int(round((v_start - start) * ts))
            skip = min(skip, max(0, play - 1))
            edits.append((_to_movie(play - skip, ts), delay + skip))
        movie_duration = max(movie_duration, edits_duration(edits))
        traks.append(t.init.rebuild_trak(new_id, media_dur, edits, t.tables(offsets_by_track[new_id - 1], use_co64)))
    mvhd = struct.pack(">IIIIIIH10x", 0, 0, 0, MOVIE_TIMESCALE, min(movie_duration, 0xFFFFFFFF), 0x00010000, 0x0100)
    mvhd += struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
    mvhd += b"\x00" * 24 + struct.pack(">I", len(tracks) + 1)
    return box("moov", box("mvhd", mvhd) + b"".join(traks)), movie_duration


FTYP = box("ftyp", b"isom" + struct.pack(">I", 0x200) + b"isomiso2avc1mp41")


def remux_clip(clip_dir: Path, out_path: Path, progress=None, cancel=None):
    """Write the clip as a regular MP4. Returns a dict with details."""
    tracks = _load_tracks(Path(clip_dir))
    # Interleave fragment runs of all tracks by time so players read smoothly.
    order = []
    for ti, t in enumerate(tracks):
        for ri, run in enumerate(t.runs):
            order.append((run[5] / t.init.timescale, ti, ri))
    order.sort()
    payload = sum(run[2] for t in tracks for run in t.runs)
    use_co64 = payload + 64 * 1024 * 1024 > 0xFFFFFFFF
    mdat_header = 16 if payload + 16 > 0xFFFFFFFF else 8

    def layout(moov_size):
        pos = len(FTYP) + moov_size + mdat_header
        offs = [[0] * len(t.runs) for t in tracks]
        for _, ti, ri in order:
            offs[ti][ri] = pos
            pos += tracks[ti].runs[ri][2]
        return offs

    dummy = [[0] * len(t.runs) for t in tracks]
    moov, _ = _build_moov(tracks, dummy, use_co64)
    moov, duration = _build_moov(tracks, layout(len(moov)), use_co64)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(f".{out_path.name}.part")
    done = 0
    handles = {}
    try:
        with open(tmp, "wb") as out:
            out.write(FTYP)
            out.write(moov)
            if mdat_header == 16:
                out.write(struct.pack(">I4sQ", 1, b"mdat", payload + 16))
            else:
                out.write(struct.pack(">I4s", payload + 8, b"mdat"))
            for _, ti, ri in order:
                path, offset, length, *_ = tracks[ti].runs[ri]
                fh = handles.get(path)
                if fh is None:
                    for old in list(handles.values()):
                        old.close()
                    handles.clear()
                    fh = handles[path] = open(path, "rb")
                fh.seek(offset)
                left = length
                while left:
                    block = fh.read(min(COPY_BLOCK, left))
                    if not block:
                        raise ClipError(f"{path.name} is shorter than expected")
                    out.write(block)
                    left -= len(block)
                    done += len(block)
                    if progress:
                        progress(done, payload)
                    if cancel is not None and cancel.is_set():
                        raise ClipError("Cancelled")
        os.replace(tmp, out_path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    finally:
        for fh in handles.values():
            fh.close()
    video = next(t for t in tracks if t.init.handler == "vide")
    return {
        "path": str(out_path),
        "size": out_path.stat().st_size,
        "seconds": round(duration / MOVIE_TIMESCALE, 2),
        "width": video.init.width,
        "height": video.init.height,
        "tracks": [t.init.handler for t in tracks],
    }


# --------------------------------------------------------------------------
# Background export job (one at a time)


def safe_name(text, fallback="Clip"):
    text = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", str(text or "")).strip(" .")
    text = re.sub(r"\s+", " ", text)
    return text[:80] or fallback


def output_name(clip_dir: Path, game_name=None):
    m = CLIP_DIR_RE.match(Path(clip_dir).name)
    stamp = ""
    if m:
        d, c = m.group(2), m.group(3)
        stamp = f"{d[:4]}-{d[4:6]}-{d[6:]} {c[:2]}-{c[2:4]}-{c[4:]}"
        fallback = f"Steam clip {m.group(1)}"
    else:
        fallback = "Steam clip"
    return f"{safe_name(game_name, fallback)} {stamp}".strip() + ".mp4"


def clip_source_bytes(clip_dir: Path):
    total = 0
    newest = 0.0
    for v in _video_dirs(Path(clip_dir)):
        for f in v.iterdir():
            if f.name.endswith(".m4s"):
                st = f.stat()
                total += st.st_size
                newest = max(newest, st.st_mtime)
    return total, newest


class ClipExporter:
    def __init__(self):
        self.lock = threading.Lock()
        self.job = None
        self.cancel = threading.Event()

    def snapshot(self):
        with self.lock:
            return dict(self.job) if self.job else None

    def start(self, clip_dir: Path, out_dir: Path, game_name=None, on_done=None):
        with self.lock:
            if self.job and self.job.get("state") == "working":
                if self.job.get("id") == str(clip_dir):
                    return dict(self.job)
                raise ClipError("Another clip is being prepared")
            out_path = Path(out_dir) / output_name(clip_dir, game_name)
            src_bytes, newest = clip_source_bytes(clip_dir)
            if out_path.is_file() and out_path.stat().st_mtime >= newest and out_path.stat().st_size >= src_bytes * 0.9:
                self.job = {"id": str(clip_dir), "state": "done", "percent": 100, "path": str(out_path),
                            "name": out_path.name, "size": out_path.stat().st_size, "error": None, "reused": True}
                job = dict(self.job)
            else:
                try:
                    free = os.statvfs(out_dir if Path(out_dir).exists() else Path(out_dir).parent)
                    if free.f_bavail * free.f_frsize < src_bytes + 64 * 1024 * 1024:
                        raise ClipError("Not enough free space on the Deck for this clip")
                except (OSError, AttributeError):
                    pass
                self.cancel.clear()
                self.job = {"id": str(clip_dir), "state": "working", "percent": 0, "path": str(out_path),
                            "name": out_path.name, "size": src_bytes, "error": None, "started": time.time()}
                job = dict(self.job)
                threading.Thread(target=self._run, args=(Path(clip_dir), out_path, on_done), daemon=True).start()
                return job
        if on_done:
            on_done(job)
        return job

    def _run(self, clip_dir, out_path, on_done):
        def progress(done, total):
            with self.lock:
                if self.job:
                    self.job["percent"] = round(done * 100.0 / total, 1) if total else 100
        try:
            info = remux_clip(clip_dir, out_path, progress, self.cancel)
            with self.lock:
                self.job.update(state="done", percent=100, size=info["size"], seconds=info["seconds"])
                job = dict(self.job)
            if on_done:
                on_done(job)
        except Exception as exc:  # noqa: BLE001 - reported to the panel
            with self.lock:
                self.job.update(state="error", error=str(exc) or exc.__class__.__name__)

    def stop(self):
        self.cancel.set()
