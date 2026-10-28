# Put the Southsites landing page live on southsites.ca

Brand is Southsites (Gabriel's pick, Oct 28 2026), domain southsites.ca (bought at Porkbun Oct 28), email
contact@southsites.ca, sign-off "Jan Gabriel, Southsites". It replaces Whyte Web (whyteweb.ca was never bought).
yegsites.ca belongs to a different Edmonton web design business, so the page never uses "YEG Sites". yegsites.com is ours
and only forwards to southsites.ca.

The repo folder and GitHub repo are still called `yegsites`. That is only a path; nothing public shows it.

## Rename the brand later

```bash
cd C:/dev/sites/yegsites
py set_brand.py "New Name" newname.ca
```

It swaps the name and domain in every page, demo, 404, sitemap, robots and this file, and writes `CNAME`. Then re-render
`og.png` and `apple-touch-icon.png` (ask Claude) and commit.

## Right now (Oct 28)

- Steps 1 to 4 are done: southsites.ca DNS, contact@southsites.ca forward, Pages on southsites.ca with HTTPS, and
  yegsites.com 301 to https://southsites.ca, SPF (Porkbun + Google) and DMARC p=none. Still open: Gmail "Send mail as"
  (step 2, you).
- Done Oct 28: southsites.ca TXT is
  `v=spf1 include:_spf.porkbun.com include:_spf.google.com ~all`, `_dmarc` TXT is
  `v=DMARC1; p=none; rua=mailto:contact@southsites.ca`.

## 1. DNS for southsites.ca (5 min)

Porkbun, Domain Management, southsites.ca, DNS. Delete the parking ALIAS (`southsites.ca` -> pixie.porkbun.com) and the
wildcard CNAME (`*.southsites.ca` -> pixie.porkbun.com). Add:

| Type | Host | Answer |
|---|---|---|
| A | (blank) | 185.199.108.153 |
| A | (blank) | 185.199.109.153 |
| A | (blank) | 185.199.110.153 |
| A | (blank) | 185.199.111.153 |
| CNAME | www | gperalta-dev.github.io |

## 2. Email (2 min)

Porkbun, southsites.ca, Email Forwarding: `contact` delivers to `gperaltainbox@gmail.com`. Porkbun adds its forwarding
MX and SPF records itself; check they are in the DNS list afterwards (MX fwd1.porkbun.com and fwd2.porkbun.com, TXT
`v=spf1 include:_spf.porkbun.com ~all`).

To reply as contact@southsites.ca from Gmail:
1. myaccount.google.com, Security, App passwords: make one called "Southsites mail".
2. Gmail, Settings, Accounts and Import, "Send mail as", Add another email address. Name "Jan Gabriel", address
   contact@southsites.ca, leave "Treat as an alias" ticked.
3. SMTP server smtp.gmail.com, port 587, username gperaltainbox@gmail.com, password = the app password, TLS.
4. Gmail emails a code to contact@southsites.ca, which forwards back to your inbox. Paste it.
5. Optional: same screen, "When replying to a message", pick "Reply from the same address the message was sent to".

## 3. Switch Pages to the new domain (5 min, after step 1)

```bash
cd C:/dev/sites/yegsites
printf 'southsites.ca\n' > CNAME && git commit -am "pages: southsites.ca" && git push
gh api -X PUT repos/gperalta-dev/yegsites/pages -f cname=southsites.ca
```

Wait 10 to 30 minutes for the certificate, then:

```bash
gh api -X PUT repos/gperalta-dev/yegsites/pages -F https_enforced=true
```

## 4. yegsites.com forwards to southsites.ca (3 min, after step 3)

Porkbun, yegsites.com, URL Forwarding: forward to `https://southsites.ca`, permanent (301), include path, with and without
www. Porkbun replaces the A and www records itself. The contact@yegsites.com email forward can stay; nothing public uses it.

## 5. Turn on the form (5 min, you sign up)

Until this is done, the form opens a text message to 825-461-5061 with the visitor's details, and the button says
"Continue in Messages".

1. web3forms.com, create a free access key with gperaltainbox@gmail.com (the key is public by design, it is safe in the page).
2. In `index.html`, find `id="w3f-key"` and paste the key between the quotes of `value=""`.
3. Commit and push: `git commit -am "turn on web3forms" && git push`.
4. Send yourself a test request from your phone and check it lands in Gmail. The button now says "Send my request".

## Before you send the link

- Founding price "first 3 clients": change the line once 3 clients have paid.
- Search Console: add southsites.ca as a Domain property with whichever Google account should own it, then add its TXT
  record in Porkbun DNS.
