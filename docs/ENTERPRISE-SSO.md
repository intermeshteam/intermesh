# Signing in with a company directory

"We need SSO" is rarely about a protocol. It is about not creating five
thousand accounts by hand, and about a departure revoking access on its own —
in the directory the company already runs, not in yet another user list.

Two ways to get there. The first is free and covers most companies; the second
is the one procurement asks for by name.

---

## Microsoft Entra ID and Google Workspace (free)

A company running Entra ID (formerly Azure AD) or Google Workspace already
holds every employee in one directory. Connecting to it through OAuth gives
you the thing that matters: people sign in with their work account, and
disabling that account removes their access here too.

The portal already renders the buttons. **They only appear once the provider
is enabled** — see [Why disabled providers are hidden](#why-disabled-providers-are-hidden).

### Microsoft Entra ID

1. In the [Azure portal](https://portal.azure.com), register an application
   under **Microsoft Entra ID → App registrations → New registration**.
2. For **Supported account types**, choose *Accounts in this organizational
   directory only* if the portal should be limited to your company.
3. Set the redirect URI to:
   ```
   https://<your-project-ref>.supabase.co/auth/v1/callback
   ```
4. Create a client secret under **Certificates & secrets**.
5. In the Supabase dashboard, **Authentication → Providers → Azure**: paste the
   Application (client) ID and the secret, then enable it.
6. **To restrict sign-in to your tenant**, set the Azure Tenant URL to:
   ```
   https://login.microsoftonline.com/<your-tenant-id>
   ```
   Leave it empty and Supabase uses Microsoft's `common` tenant — meaning *any*
   Microsoft account can sign in, including personal ones. For a company
   deployment that is almost certainly not what you want.

### Google Workspace

Same shape: create OAuth credentials in the Google Cloud console, use the same
Supabase callback URL, then enable the Google provider in the dashboard.

Restricting to one Workspace domain is not part of the OAuth flow — Google
will let any Google account through. If you need that boundary enforced,
either use Entra ID with a tenant URL, or add a check on the email domain
after sign-in.

---

## SAML 2.0 (Supabase Pro and above)

Supabase supports SAML 2.0 on **Pro and above**. It is enabled once on the
Auth Providers page, then each identity provider is added with the Supabase
CLI rather than the dashboard:

```bash
supabase sso add --project-ref <ref> --type saml --metadata-url <idp-metadata>
supabase sso list --project-ref <ref>
```

Worth knowing before committing to it:

- It is a **paid plan**, so it is a cost decision, not just a technical one.
- Configuration happens through the CLI, which means it is a deployment step
  rather than something an administrator does in a web console.
- Nothing in this repository depends on it. The portal reads whichever
  identity a session carries; SAML changes where that identity comes from,
  not how the Control Plane behaves.

Reach for it when a customer names SAML in a requirements document. Until
then, Entra ID covers the same need without the plan.

---

## Why disabled providers are hidden

The sign-in page only shows providers the Supabase project actually has
enabled. It asks `/auth/v1/settings`, which answers with the anon key the
browser already holds.

This is not cosmetic. When a provider is disabled, `signInWithOAuth` **does
not fail** — it builds a URL and navigates. The visitor leaves the site and
lands on raw JSON served by the Supabase domain:

```json
{"code":400,"error_code":"validation_failed","msg":"Unsupported provider: provider is not enabled"}
```

There is no error for the page to catch and nothing to bring them back.
Verified against a live project — which is why the buttons are filtered rather
than rendered and left to fail.

Enable a provider in the Supabase dashboard and its button appears on the next
page load. Nothing to redeploy.

---

## What this does not cover

**Agents do not sign in this way.** SSO here is for humans reaching the
Control Plane. Agents authenticate to a hub with API keys, which is the right
mechanism for programs — see
[the remote-hub guide](REMOTE-HUB.md#identity-who-gets-to-declare-their-own-roles).

**No SCIM provisioning.** Accounts are created on first sign-in, not
synchronised ahead of time from the directory. Disabling someone in Entra ID
stops them signing in; it does not delete the row here.

**Roles are not read from the directory.** Group or role claims from the
identity provider are ignored. Membership and role live in the
`memberships` table and are set in the portal.
