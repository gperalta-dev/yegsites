# Put the landing page live

Next action: decide the name (step 1), then buy the domain at Porkbun. About 25 min total.

## 1. Pick the name and domain (5 min)

**Problem found on Oct 27:** yegsites.ca is not just taken. It is a live Edmonton web design business called
"YEG Sites" selling the same thing ($500 one-page sites for Edmonton small businesses). If you use YegSites, owners who
Google you find them, and they could complain that you are using their name.

| Domain | First year | Renews | Notes |
|---|---|---|---|
| **gabrielperalta.ca** (recommended) | US$8.76 | about US$11.51 | Matches the "Hi, I'm Gabriel" pitch. Yours forever, works with any brand name. |
| seeitfirst.ca | US$8.76 | about US$11.51 | Matches the headline. Generic, so check nobody local uses the name. |
| yegsites.com | about US$11.08 | about US$11.08 | Exact brand, but same name as the live yegsites.ca business. Not recommended. |
| yegsite.ca | US$8.76 | about US$11.51 | One letter off the competitor. Not recommended. |

Prices were seen on Porkbun search on Oct 27 2026, before tax. All under the $25 limit.

If you drop the YegSites name, the brand appears in: the `<title>`, og:title, the meta description, the JSON-LD block,
the nav logo, the form subject (`YegSites preview request`), the "from_name" field, the signature line and the footer of
`index.html`. Tell Claude the new name and it will swap all of them.

## 2. Buy it on Porkbun (5 min, you do this)

1. porkbun.com, search the domain, add to cart, check out with the Money Town card. Turn off auto-renew add-ons you don't want.
2. Log the spend in `ledger/ledger.csv` the same day: date, town `local-studio`, amount, `Porkbun`, `landing page domain`.

## 3. Point the domain at GitHub Pages (5 min)

Porkbun: Account, Domain Management, the domain, **DNS**. Delete the default parking records (the ALIAS and CNAME that point
to `pixie.porkbun.com`). Then add:

| Type | Host | Answer |
|---|---|---|
| A | (blank) | 185.199.108.153 |
| A | (blank) | 185.199.109.153 |
| A | (blank) | 185.199.110.153 |
| A | (blank) | 185.199.111.153 |
| CNAME | www | gperalta-dev.github.io |

Leave TTL at the default. Do not turn on Porkbun URL forwarding.

## 4. Create the repo and turn on Pages (5 min)

If the domain is not gabrielperalta.ca, put the real domain in the `CNAME` file first (one line, no `https://`), then commit.

```bash
cd C:/dev/sites/yegsites
gh repo create gperalta-dev/yegsites --public --source . --push
gh api -X POST repos/gperalta-dev/yegsites/pages -f "source[branch]=main" -f "source[path]=/"
gh api -X PUT repos/gperalta-dev/yegsites/pages -f cname=gabrielperalta.ca
```

Wait 10 to 30 minutes for DNS and the certificate, then force HTTPS:

```bash
gh api -X PUT repos/gperalta-dev/yegsites/pages -F https_enforced=true
```

Check: `https://gabrielperalta.ca` and `https://www.gabrielperalta.ca` both load the page with a lock icon.

## 5. Turn on the form (5 min, you sign up)

Until this is done, the form opens a text message to 825-461-5061 with the visitor's details, and the button says
"Continue in Messages". That works on phones but not on most laptops.

1. web3forms.com, create a free access key with gperaltainbox@gmail.com (the key is public by design, it is safe in the page).
2. In `index.html`, find `id="w3f-key"` and paste the key between the quotes of `value=""`.
3. Commit and push: `git commit -am "turn on web3forms" && git push`.
4. Send yourself a test request from your phone and check it lands in Gmail. The button now says "Send my request".

## Before you send the link

- Add a real photo of yourself if you have one (replaces the GP circle in the About section).
- Founding price "first 3 clients": change the line once 3 clients have paid.
