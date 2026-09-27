# pf-debate hub helper (Chrome extension)

Adds the login-only data to the tournament hub at https://debate.peshcompsci.org: judge paradigms with a quick summary, a judge's voting record, and whether an opponent disclosed on OpenCaselist.

It uses the Tabroom and OpenCaselist sessions already in your browser. Your password never leaves your browser, and nothing is sent to pf-debate's server. The extension only answers the hub's own pages.

## Install (free, about 1 minute)
1. Download this `extension` folder, or the zip from the latest GitHub release, and unzip it.
2. In Chrome, go to `chrome://extensions` and turn on **Developer mode** (top right).
3. Click **Load unpacked** and pick the `extension` folder.
4. Log in at tabroom.com (for paradigms) and opencaselist.com (for disclosure) in the same browser.
5. Open the hub and follow an entry. The judge and opponent cards fill in.

## Permissions
- `cookies`: reads only your `TabroomToken` cookie, to call Tabroom's official API as you.
- Hosts: api.tabroom.com, www.tabroom.com (to read that cookie), api.opencaselist.com, and the hub.

## What it calls
- `GET https://api.tabroom.com/v1/rest/paradigms/{personId}` returns the paradigm.
- `GET https://api.tabroom.com/v1/rest/paradigms/{personId}/record` returns the judge's voting record.
- `GET https://api.opencaselist.com/v1/search?q=...` searches the current HS PF caselist.
