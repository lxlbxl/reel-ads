# Publishing a finished Reel to Instagram/Facebook (via Composio)

Optional final step -- only relevant once a video is approved and the user
asks for it to go live. This is a public, effectively-irreversible action:
confirm the exact caption with the person before publishing, every time,
even if a near-identical caption was approved for a previous video in the
same campaign.

## 1. Get the file to a public URL

Both Instagram's and Facebook's Graph API tools take a `video_url` /
`file_url`, not a local file. See `url_hosting.md` for the upload + verify
steps (litterbox over tmpfiles -- tmpfiles' direct-download link redirects
to a landing page and will fail async ingestion).

## 2. Confirm the target account -- don't trust "default"

Discover accounts read-only first:

```
FACEBOOK_LIST_MANAGED_PAGES        -- returns every Page the connection can post to
INSTAGRAM_GET_USER_INFO(ig_user_id="me")  -- confirms the *default* IG account
```

**A Composio connection can hold multiple IG business accounts, and the
"default" one is not necessarily the brand you're posting for.** In this
project's connection, the default account is a different client entirely
(`slaexports`) while `maids_ng` is a secondary account on the same
connection. Any Instagram call that omits an explicit `account` argument (or
uses `ig_user_id="me"`) posts to whichever account is flagged `is_default`
in the connection listing -- silently, no error. Always pass the confirmed
numeric `ig_user_id` explicitly, and pass the Composio `account` alias
explicitly on every tool call for this project (e.g.
`account: "instagram_comid-lunt"`), never rely on the default.

## 3. Instagram Reel -- two-step create then publish

```
INSTAGRAM_POST_IG_USER_MEDIA(
  ig_user_id=<confirmed numeric id>,
  media_type="REELS",
  video_url=<verified public URL>,
  share_to_feed=true,
  caption=<approved caption>,
)
# -> returns {id: creation_id}

INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH(
  ig_user_id=<same id>,
  creation_id=<from previous step>,
  max_wait_seconds=240,
  poll_interval_seconds=5,
)
# -> polls container status internally; video processing commonly takes 30-120s
```

Use `max_wait_seconds` >= 180 for anything near or over 60s of video --
processing time scales with duration and a short timeout will report failure
on a container that actually finishes a few seconds later.

## 4. Facebook Page video post -- single call, published immediately

```
FACEBOOK_CREATE_VIDEO_POST(
  page_id=<from FACEBOOK_LIST_MANAGED_PAGES>,
  file_url=<same verified public URL>,
  published=true,
  title=<short title>,
  description=<caption -- can differ slightly from IG's>,
)
```

Facebook takes one shot, no separate publish step. A returned `id` does not
guarantee full processing succeeded -- some responses carry an
`unsuccessful` flag independent of the HTTP status; check for it rather than
assuming success from a 200.

## 5. Verify what actually posted -- read the caption back, don't assume the write succeeded

Composio tool descriptions sometimes carry stale advice (e.g. one schema
claims hashtags need `%23` URL-encoding in the caption field -- that was
**wrong** for the actual publish path tested here; literal `#tags` in the
caption string posted correctly with real `#` characters, emoji, em-dashes,
keycap digits, and the naira sign all intact). Don't trust a tool's own
schema description over an actual verification read:

```
INSTAGRAM_GET_IG_MEDIA(ig_media_id=<published id>, fields="id,caption,media_type,media_product_type,permalink,timestamp")
FACEBOOK_GET_PAGE_POSTS(page_id=<id>, limit=3, fields="id,message,created_time,permalink_url")
```

Compare the returned `caption`/`message` character-for-character against
what was sent. If they don't match, fix the encoding and re-check on the
*next* post rather than deleting and reposting the current one (deleting a
public post is its own irreversible action -- don't do it reflexively to
fix a cosmetic mismatch that a caption edit could resolve instead, and ask
before deleting anything already live).

## Caption/copy discipline

Every claim in the caption should trace to something already established as
real for the brand -- pricing, SLAs, guarantees actually offered (see
`brand_claims.md`). For maids.ng specifically: NIN verification, the
₦20,000 flat fee, the 48-hour match window, and the 10-day free-replacement
guarantee are all confirmed real (visible in the brand's own existing FB
posts / ad library) -- reuse these, don't invent new numbers or outcomes for
a caption that a script-writing pass didn't already vet.
