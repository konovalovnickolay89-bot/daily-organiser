# In-app privacy link (not applied)

Google’s branding page asks for a privacy notice inside the product, as well as the public privacy URL. The appointments footnote today is “Read only. This is not a calendar.” Settings say the diary is read-only. Neither links to the privacy policy.

This file is the proposal. It does not change the app, add a route, or bypass Cloudflare Access. The household app stays behind Access. The link, when it exists, points at the public info host.

## Do not add it until the privacy URL is public

`https://organiser-info.apidiscoverysolution.uk/privacy.html` does not resolve yet. A link in the live app before that URL returns 200, with no Access login, would be a broken notice. discovery-system’s hosting yes, and the access tests in `HOSTING-PLAN.md`, come first.

## Exact words

One sentence, in two places, linking to that privacy URL and nowhere else:

“How calendar data is handled is in the privacy policy.”

The link text is “privacy policy”. The address is `https://organiser-info.apidiscoverysolution.uk/privacy.html`. It opens in the same tab. No button, no form, no token.

## Where

1. `frontend/src/modules/brief/BriefSection.tsx`, after the existing footnote, only when `section.key === "appointments"`. Leave the API footnote “Read only. This is not a calendar.” as it is.
2. `frontend/src/arrival/ThemeCard.tsx`, as its own sentence after the diary paragraph that begins “The diary is read-only.” Do not add the link to the commute sentence in that paragraph.

Both sit on screens a person already admitted by Access can see. Neither is a path on `organiser.apidiscoverysolution.uk`, and neither is a secret URL.
