# Put the Whyte Web landing page live on whyteweb.ca

Next action: buy whyteweb.ca on Porkbun (step 1, you do this). Then steps 2 to 6, about 25 min.

Brand is Whyte Web (Oct 27 2026). yegsites.com stays unused for the business. yegsites.ca belongs to a different Edmonton
web design business, so the page does not use that name anywhere.

## 0. Set the name: DONE Oct 27 (Whyte Web, whyteweb.ca)

The brand and domain are placeholders until the name is picked. One command swaps them everywhere (every page, the demos,
404, sitemap, robots, this file) and writes the CNAME file:

```bash
cd C:/dev/sites/yegsites
py set_brand.py "New Name" newname.ca
```

Then ask Claude to re-render `og.png` (the link preview image) with the new name, and commit.

## Right now

- The GitHub repo `gperalta-dev/yegsites` is live on https://yegsites.com with the OLD YegSites version (pushed earlier today).
- The rebrand is committed locally only. It is not pushed, because pushing it with the new `CNAME` file moves GitHub Pages
  to whyteweb.ca, and that domain does not point anywhere until you buy it.

## 1. Buy whyteweb.ca (5 min, you do this)

Porkbun, search whyteweb.ca, check out with the Money Town card. Log it in `ledger/ledger.csv` the same day.

## 2. DNS for whyteweb.ca (5 min, Claude can do this in your Chrome)

Porkbun, Domain Management, whyteweb.ca, DNS. Delete the parking ALIAS and wildcard CNAME. Keep the MX and SPF records
(they run Porkbun's free email forwarding). Add:

| Type | Host | Answer |
|---|---|---|
| A | (blank) | 185.199.108.153 |
| A | (blank) | 185.199.109.153 |
| A | (blank) | 185.199.110.153 |
| A | (blank) | 185.199.111.153 |
| CNAME | www | gperalta-dev.github.io |

## 3. Email (2 min, Claude can do this in your Chrome)

Porkbun, whyteweb.ca, Email, Email Forwarding: `contact` delivers to `gperaltainbox@gmail.com`. The page already shows
contact@whyteweb.ca.

## 4. Push and switch Pages to the new domain (5 min)

```bash
cd C:/dev/sites/yegsites
git push origin main
gh api -X PUT repos/gperalta-dev/yegsites/pages -f cname=whyteweb.ca
```

Wait 10 to 30 minutes for the certificate, then:

```bash
gh api -X PUT repos/gperalta-dev/yegsites/pages -F https_enforced=true
```

Optional, so the repo name matches the brand (GitHub redirects the old name):

```bash
gh repo rename <new-repo-name> -R gperalta-dev/yegsites --yes
```

## 5. What to do with yegsites.com

Once Pages moves, yegsites.com shows a GitHub "site not found" page. Pick one:
- Porkbun URL forwarding: yegsites.com to https://whyteweb.ca (permanent, 301). Old links keep working.
- Or delete its A and CNAME records and let it sit unused until it expires on 2027-10-27 (turn off auto-renew).

The contact@yegsites.com forward to Gmail can stay or be deleted. Nothing on the new page uses it.

## 6. Turn on the form (5 min, you sign up)

Until this is done, the form opens a text message to 825-461-5061 with the visitor's details, and the button says
"Continue in Messages".

1. web3forms.com, create a free access key with gperaltainbox@gmail.com (the key is public by design, it is safe in the page).
2. In `index.html`, find `id="w3f-key"` and paste the key between the quotes of `value=""`.
3. Commit and push: `git commit -am "turn on web3forms" && git push`.
4. Send yourself a test request from your phone and check it lands in Gmail. The button now says "Send my request".

## Before you send the link

- Add a real photo of yourself if you have one (replaces the GP circle in the About section).
- Founding price "first 3 clients": change the line once 3 clients have paid.
- Search Console: add whyteweb.ca as a Domain property with whichever Google account should own it, then add its TXT
  record in Porkbun DNS.
