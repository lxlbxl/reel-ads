# Getting a video from local disk to a URL Meta/other APIs can fetch

Several downstream steps need the finished MP4 (or a WAV/MP3) reachable at a
public HTTPS URL rather than as local bytes: Meta's Graph API (`video_url` /
`file_url` params for Instagram and Facebook), and occasionally a VO tool that
hands back a presigned link instead of raw audio (see `vo_sync.md`). Two
temp-hosting services were tested directly from this pipeline's environment;
one has a sharp edge, the other doesn't.

## tmpfiles.org -- works for upload, wrong link for machine fetch

```bash
curl -sS -F "file=@video.mp4" https://tmpfiles.org/api/v1/upload
# {"status":"success","data":{"url":"https://tmpfiles.org/wQw6RZf9uaXH/video.mp4"}}
```

The obvious move -- swap `tmpfiles.org/` for `tmpfiles.org/dl/` to get a
"direct download" link -- **does not return the file**. It 302-redirects to
a **time-signed URL that regenerates on every request**:

```
HTTP/1.1 302 Found
Location: https://tmpfiles.org/wQw6RZf9uaXH/maids_explainer60.mp4
```

...and even the page at the original (non-`/dl/`) URL serves an HTML
landing page, not the video, when curled directly (no browser, no cookies).
An API that fetches the URL asynchronously (Meta's ingestion is
async -- it polls a container, it doesn't fetch synchronously in your
request) can easily hit a stale or re-signed link and fail with a fetch
error. **Don't use tmpfiles for anything an external API will fetch later**;
it's fine for handing a link to a human to click immediately.

## litterbox.catbox.moe -- stable direct link, verify before using

```bash
curl -sS -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@video.mp4" \
  https://litterbox.catbox.moe/resources/internals/api.php
# -> https://litter.catbox.moe/4x5er0.mp4   (plain text response, just the URL)
```

`time` is one of `1h`, `12h`, `24h`, `72h` -- pick the shortest one that
comfortably covers however long the downstream API needs to fetch and
process the file (Meta's video ingestion commonly takes 30-120s, so even 1h
is generous margin -- but 72h gives room to retry a failed publish without
re-uploading).

**Always verify before handing the link to another API** -- a wrong upload
or an expired link fails silently downstream and is expensive to debug from
the other side:

```bash
curl -sSI "https://litter.catbox.moe/4x5er0.mp4" | grep -iE "^HTTP|content-type|content-length|location"
# HTTP/1.1 200 OK
# Content-Type: video/mp4
# Content-Length: 26375404
# (no Location header -- confirms no redirect)

curl -sS -r 0-11 "https://litter.catbox.moe/4x5er0.mp4" | xxd | head -1
# 00000000: 0000 0020 6674 7970 6973 6f6d            ... ftypisom
```

Check three things: status is `200` with no `Location` header (a redirect
here means the same tmpfiles-style problem), `Content-Type` matches the file
(`video/mp4`, `audio/mpeg`, etc.), and the first bytes match the format's
magic number (`ftyp` a few bytes into an MP4, `ID3` or `\xff\xfb` for MP3).

## General rule for any temp-hosting service

Before wiring a URL into an API call that will fetch it *later* (not in the
same request), always confirm:

1. `curl -sSI <url>` returns `200` with **no redirect** -- Location header
   present means it's a landing page, not the file.
2. `Content-Type` is the actual media type, not `text/html`.
3. First bytes match the file's magic number, not `<!DOCTYPE html>`.
4. The link's TTL comfortably outlasts the slowest step that will fetch it
   (async video ingestion, retries after a transient failure).

A link that looks right in a browser (which follows redirects and renders
nicely) can still fail an API's raw HTTP fetch. Curl it exactly the way the
downstream service will.

## Cleanup note

These are public, unauthenticated, third-party hosts -- anyone with the URL
can access the file for its TTL. Fine for a short-lived hop to a same-day
publish; never use for anything containing secrets, unreleased material past
its embargo, or content the client hasn't approved. The file falls off the
host automatically after the requested `time` window; no action needed.
