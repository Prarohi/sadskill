# Third-Party Notices & Licenses

`sadskill` curates and vendors battle-tested skills, design systems, protocols, and engineering patterns under one unified architecture. All vendored files in `skills/sadskill/vendor/` are attributed below with their original license terms.

| Component / Skill | Upstream Repository / Author | License | Integration Method |
|---|---|---|---|
| **Codebase Design & TDD** | [Matt Pocock](https://github.com/mattpocock) | MIT | Neutralized reference (`*.ref.md`) |
| **Superpowers** | [obra/superpowers](https://github.com/obra/superpowers) | MIT | Neutralized reference (`*.ref.md`) |
| **Karpathy Guidelines** | [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | MIT | Neutralized reference (`*.ref.md`) |
| **Humanizer** | [blader/humanizer](https://github.com/blader/humanizer) | MIT | Core protocol & reference |
| **Attention Span** | [alexgreensh/attention-span](https://github.com/alexgreensh/attention-span) | MIT | Core protocol & reference |
| **Impeccable Design** | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | MIT | Neutralized reference (`*.ref.md`) |
| **Taste Skill** | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | MIT | Neutralized reference (`*.ref.md`) |
| **Shadcn UI Patterns** | [shadcn/ui](https://github.com/shadcn-ui/ui) | MIT | Neutralized reference (`*.ref.md`) |
| **Vercel Agent Skills** | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | Apache-2.0 | Neutralized reference (`*.ref.md`) |
| **Anthropic Skills** | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 | Neutralized reference (`*.ref.md`) |
| **Supabase Agent Skills** | [supabase/agent-skills](https://github.com/supabase/agent-skills) | Apache-2.0 | Neutralized reference (`*.ref.md`) |
| **Marketing Skills** | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | MIT | Neutralized reference (`*.ref.md`) |
| **OpenAI Skills** | [openai/skills](https://github.com/openai/skills) | MIT | Neutralized reference (`*.ref.md`) |
| **iOS Simulator Skill** | [conorluddy/ios-simulator-skill](https://github.com/conorluddy/ios-simulator-skill) | MIT | Neutralized reference (`*.ref.md`) |
| **Claude-Octopus** | [nyldn/claude-octopus](https://github.com/nyldn/claude-octopus) | MIT | Neutralized reference (`*.ref.md`) |
| **Cloudflare Skills** | [cloudflare/skills](https://github.com/cloudflare/skills) | MIT / Apache-2.0 | Neutralized reference (`*.ref.md`) |
| **Waza Craftsmanship** | [tw93/Waza](https://github.com/tw93/Waza) | MIT | Neutralized reference (`*.ref.md`) |
| **Addy Osmani Skills** | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Apache-2.0 | Neutralized reference (`*.ref.md`) |
| **Integralist Skills** | [Integralist/agent-skills](https://github.com/Integralist/agent-skills) | Apache-2.0 | Neutralized reference (`*.ref.md`) |
| **Everything Computer Code (ECC)** | ECC Community | MIT | Neutralized reference (`*.ref.md`) |
| **OWASP Security Guides** | [OWASP Foundation](https://owasp.org) | CC-BY-SA 4.0 / Open | Neutralized reference (`*.ref.md`) |
| **Animation & Motion Skills** | Motion & Animation Community | MIT | Neutralized reference (`*.ref.md`) |
| **Modern Web Guidance** | Modern Web Best Practices Community | MIT | Neutralized reference (`*.ref.md`) |

---

### Linked platform documentation

The task guides in `skills/sadskill/references/` are original Sadskill guidance linking to official [Supabase](https://supabase.com/docs), [Vercel](https://vercel.com/docs), and [Bklit UI](https://ui.bklit.com/docs) documentation. No upstream component source or complete third-party skill is copied into those guides. A consuming project that installs registry components must retain the upstream notices and check the license for the specific code it adds.

### Frontmatter Neutralization Notice

In accordance with agent discovery standards, all vendored reference files within `skills/sadskill/vendor/` have their top-level frontmatter neutralised (by utilizing `.ref.md` suffixes or removing primary `name:` headers). This ensures that agent tools (such as `skills` CLI, Codex, Claude Code, Cursor) discover and register exactly one primary root skill: `sadskill`.
