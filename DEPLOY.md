# Put the landing page live on yegsites.com

Next action: run the 3 commands in step 2. About 10 min total.

The domain purchase is handled separately (Town Hall session with Gabriel). This file only covers DNS, GitHub Pages and the form.

Note: yegsites.ca belongs to a live Edmonton web design business called "YEG Sites". Gabriel chose yegsites.com knowing this
(Oct 27 2026). Expect the odd owner to mix the two up.

## 1. Point yegsites.com at GitHub Pages: DONE Oct 27 (parking ALIAS and wildcard CNAME deleted, records below added, Porkbun mail-forwarding MX and SPF kept)

Porkbun: Account, Domain Management, yegsites.com, **DNS**. Delete the default parking records (the ALIAS and CNAME that point
to `pixie.porkbun.com`). Then add:

| Type | Host | Answer |
|---|---|---|
| A | (blank) | 185.199.108.153 |
| A | (blank) | 185.199.109.153 |
| A | (blank) | 185.199.110.153 |
| A | (blank) | 185.199.111.153 |
| CNAME | www | gperalta-dev.github.io |

Leave TTL at the default. Do not turn on Porkbun URL forwarding.

## 2. Create the repo and turn on Pages (5 min)

The repo already has a `CNAME` file containing `yegsites.com`.

```bash
cd C:/dev/sites/yegsites
gh repo create gperalta-dev/yegsites --public --source . --push
gh api -X POST repos/gperalta-dev/yegsites/pages -f "source[branch]=main" -f "source[path]=/"
gh api -X PUT repos/gperalta-dev/yegsites/pages -f cname=yegsites.com
```

Wait 10 to 30 minutes for DNS and the certificate, then force HTTPS:

```bash
gh api -X PUT repos/gperalta-dev/yegsites/pages -F https_enforced=true
```

Check: `https://yegsites.com` and `https://www.yegsites.com` both load the page with a lock icon.

## 3. Turn on the form (5 min, Gabriel signs up)

Until this is done, the form opens a text message to 825-461-5061 with the visitor's details, and the button says
"Continue in Messages". That works on phones but not on most laptops.

1. web3forms.com, create a free access key with gperaltainbox@gmail.com (the key is public by design, it is safe in the page).
2. In `index.html`, find `id="w3f-key"` and paste the key between the quotes of `value=""`.
3. Commit and push: `git commit -am "turn on web3forms" && git push`.
4. Send yourself a test request from your phone and check it lands in Gmail. The button now says "Send my request".

## Before you send the link

- Add a real photo of yourself if you have one (replaces the GP circle in the About section).
- Founding price "first 3 clients": change the line once 3 clients have paid.
