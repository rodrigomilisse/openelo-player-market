// The site's connections to outside services. Empty means "not connected": the site still works.
// See CONNECT.md for what each one needs.
export const CONFIG = {
  siteUrl: '',            // e.g. 'https://openelo.com', for share links and the sitemap
  contactEmail: '',       // shown on About and Privacy; empty keeps the placeholder
  waitlistUrl: '',        // a form endpoint that accepts POST JSON { email, country, page } (Formspree, Supabase function, Buttondown…)
  analytics: {
    plausibleDomain: '',  // Plausible: the site's domain as registered there; loads their script, no cookies
  },
};
