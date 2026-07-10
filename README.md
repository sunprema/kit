# kit

A Claude Code plugin marketplace for Sundar Nambuvel's tools. One repo, one
sibling directory per plugin — install the marketplace once, then install
just the plugin(s) you want.

```
/plugin marketplace add sunprema/kit
/plugin install bookbank@kit
```

## Plugins

- **[`bookbank/`](bookbank/)** — research-and-write BookBank books, publish
  them to the public library (`sunprema/books`), and generate a book from a
  GitHub Issue. See [`bookbank/docs/contributor-setup.md`](bookbank/docs/contributor-setup.md).

(More plugins land here over time — each lives in its own top-level
directory, listed in `.claude-plugin/marketplace.json`.)
