# Remaining Calendar setup

Nothing in this file is performed here. No secret, token, or Google call is collected. The app still has no Google OAuth callback. `POST /x/callback` is the X connection, not Calendar.

The consent-screen name is **Daily Organiser bot**. That is the name already entered. This setup does not invent another brand.

## What the email approval covers

Approved on 7 November 2026: publish `mykolakonovalov@gmail.com` as the Daily Organiser support email.

That means two places, and only those:

1. The support line on `index.html`, `privacy.html`, and `terms.html`.
2. The user-support email field on the Google consent screen, when someone later types it there. Google shows that field to people on the consent screen. It has to be an address the logged-in Cloud user can select, or a Google Group they manage. This repository does not open the console, so it cannot see whether that Gmail address is already one of those choices.

It does not approve hosting, DNS, Cloudflare, Access, Verify branding, Publish branding, or putting a refresh token anywhere.

## Consent-screen values, for a later paste

Paste these only after the access tests in `HOSTING-PLAN.md` pass. The hostname is still PROPOSED.

| Field | Value |
| --- | --- |
| App name | Daily Organiser bot |
| User support email | mykolakonovalov@gmail.com |
| Homepage | `https://organiser-info.apidiscoverysolution.uk/` |
| Privacy policy | `https://organiser-info.apidiscoverysolution.uk/privacy.html` |
| Terms of service | `https://organiser-info.apidiscoverysolution.uk/terms.html` |
| Authorized domain | `apidiscoverysolution.uk` |

The privacy string in the console and the privacy link on the homepage have to match, including `https` and `.html`.

Scopes already named for this app, and the only ones in `backend/organiser/services/diary.py`:

- `https://www.googleapis.com/auth/calendar.events.readonly`
- `https://www.googleapis.com/auth/calendar.calendarlist.readonly`

Google’s sentence for the events scope is “view events on all your calendars.” The house configuration is the primary calendar: leave `GOOGLE_CALENDAR_IDS` blank. The scope text is wider than that configuration. Do not add a write scope.

## Gates still shut

1. discovery-system yes for the Cloudflare Pages project in `HOSTING-PLAN.md`. Email approval is not that yes.
2. discovery-system publishes exactly `index.html`, `privacy.html`, `terms.html`, and `404.html` to the Pages project and the `organiser-info` DNS record. Nick approved that on 7 November 2026 at 15:41 GMT. It is not done in this repository. No Access app on that name. The app host stays behind Access. The hostname is not live until those checks pass.
3. Unauthenticated checks in `HOSTING-PLAN.md`. Not run against the live hosts here.
4. Search Console verification of `apidiscoverysolution.uk`, if it is not already verified. Unknown.
5. Authorized domain saved in the Google Auth Platform before the three URLs. Unknown.
6. Paste the table above. Then Verify branding. If it passes, Publish branding within 7 days. Not done. A pass is not guaranteed.
7. Data-access verification for the scopes, if the console asks, after branding is published. A demo may be requested. Not done.
8. In-app privacy link from `IN_APP_NOTICE.md`, only after the privacy URL returns 200 with no login. Not in the app.
9. Refresh token, client id, and client secret placed in the house environment by discovery-system. This repo must not receive them.

## Refresh token, still outside the app

Fetched 7 November 2026 from `https://developers.google.com/oauthplayground/`. The Playground still has “Use your own OAuth credentials.” Google’s page says the redirect URI to list on the OAuth client is `https://developers.google.com/oauthplayground`, that the client id and secret are sent to Google’s Playground server so it can proxy the token request, and that Playground refresh tokens are revoked after 24 hours unless your own client credentials are used. Google also says those credentials are not logged. That is Google’s statement. This page does not test it.

That redirect is on Google’s host. It is not a route in Daily Organiser. Do not add a callback to this app.

Operator steps, done in the operator’s own browser, not here:

1. On the existing External OAuth client (web application), add the Playground redirect above if it is not already there. Do not point it at `organiser.apidiscoverysolution.uk`.
2. In the Playground configuration, turn on “Use your own OAuth credentials” and enter that client’s id and secret. Do not turn on the option that puts credentials or tokens into a shareable link. Do not send that link to anyone.
3. In step 1, enter only the two scope URLs above. Authorize with the personal Google account whose primary calendar is the one to read.
4. Exchange the code. Copy the refresh token into the house environment as `GOOGLE_OAUTH_REFRESH_TOKEN`, with `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`. Leave `GOOGLE_CALENDAR_IDS` blank so the app reads `primary`.
5. Do not paste the token, the secret, or the client id into this repository, this pull request, or an email.

The app refreshes that token with `grant_type=refresh_token` and does not send a scope on the refresh. It cannot widen the grant. It also cannot, from the source, prove what the live token was granted.
