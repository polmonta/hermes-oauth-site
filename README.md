# Pol's Hermes information site

A small static site for `https://hermes.montanera.cat/`. It describes Pol's private assistant and its Google data use, including reading email and sending owner-approved messages only after separate sending permission is granted. Existing calendar access is disclosed without adding permissions. Source files alone do not establish that Pages, public HTTPS, or Google production publishing are configured.

## Local build and checks

There is no build step or dependency install. The files are served as-is.

```sh
python3 scripts/check_site.py
python3 -m unittest discover -s tests -v
python3 scripts/preview_site.py
```

Then open `http://127.0.0.1:8000/` to review the pages. The preview binds only to loopback and serves an explicit allowlist: the homepage, privacy policy, terms, and stylesheet. It does not serve `.local/`, `.git/`, scripts, tests, the README, directory listings, or symlinked files. Use `--port NUMBER` to choose a different local port.

The standard-library checker verifies structural requirements, required keywords, internal links, selected local asset references, the custom-domain file, and Git exclusion for private files. The regression tests exercise the documented preview restrictions and the demonstrated unsafe-markup cases. These checks do **not** establish privacy-policy correctness, actual runtime controls, or approval to publish.

## Deployment and verification

Review the public wording and the exact file manifest before publication. The owner confirmed model training is disabled on the account used by Hermes; the policy makes no zero-retention promise. This repository is for the Hermes information site only. Never upload `.local/`, OAuth credentials, private histories, or runtime configuration. Keep the existing `polmonta` user site for `managestate.app` untouched.

Publication sequence:

1. Use a dedicated repository for this site. Confirm that the GitHub account can create or administer it and use GitHub Pages before making any remote changes.
2. Verify the domain in GitHub Pages before adding it to a repository. Enable Pages from the dedicated repository's `main` branch and root directory only, then configure `hermes.montanera.cat` only in that repository. Do not set it on the existing user-site repository.
3. After the repository is configured, create only the `hermes` DNS `CNAME` record pointing to `polmonta.github.io`. Leave the zone apex, nameservers, email records, and all unrelated records unchanged. GitHub's guidance recommends configuring the repository domain before DNS and verifying the domain first. See [GitHub's custom-domain guidance](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).
4. Confirm DNS resolution and HTTPS for the subdomain. Then, only after content review and specific approval, configure the matching homepage, privacy-policy, and terms URLs in Google OAuth branding. Google requires the public homepage to identify the app, describe its function and data use, and link to the privacy policy. See [Google's homepage guidance](https://support.google.com/cloud/answer/13807376) and [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies).

The root `CNAME` file records the intended GitHub Pages hostname for a later branch-based deployment. It does not configure DNS, enable Pages, verify domain ownership, or make the site public by itself.
