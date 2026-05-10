# PROJECT_SNAPSHOT

? ??? ?? ?? ???? ??? ????? ??? ??????.

## 1. ?? ?? ????

- ???: `git branch --show-current`
- ????: `128`

```text
fatal: not a git repository (or any of the parent directories): .git
```

## 2. Git ?? ??

### `git status --short`
- ????: `128`

```text
fatal: not a git repository (or any of the parent directories): .git
```

### `git diff --stat`
- ????: `129`

```text
warning: Not a git repository. Use --no-index to compare two paths outside a working tree
usage: git diff --no-index [<options>] <path> <path> [<pathspec>...]

Diff output format options
    -p, --patch           generate patch
    -s, --no-patch        suppress diff output
    -u                    generate patch
    -U, --unified[=<n>]   generate diffs with <n> lines context
    -W, --[no-]function-context
                          generate diffs with <n> lines context
    --raw                 generate the diff in raw format
    --patch-with-raw      synonym for '-p --raw'
    --patch-with-stat     synonym for '-p --stat'
    --numstat             machine friendly --stat
    --shortstat           output only the last line of --stat
    -X, --dirstat[=<param1>,<param2>...]
                          output the distribution of relative amount of changes for each sub-directory
    --cumulative          synonym for --dirstat=cumulative
    --dirstat-by-file[=<param1>,<param2>...]
                          synonym for --dirstat=files,<param1>,<param2>...
    --check               warn if changes introduce conflict markers or whitespace errors
    --summary             condensed summary such as creations, renames and mode changes
    --name-only           show only names of changed files
    --name-status         show only names and status of changed files
    --stat[=<width>[,<name-width>[,<count>]]]
                          generate diffstat
    --stat-width <width>  generate diffstat with a given width
    --stat-name-width <width>
                          generate diffstat with a given name width
    --stat-graph-width <width>
                          generate diffstat with a given graph width
    --stat-count <count>  generate diffstat with limited lines
    --[no-]compact-summary
                          generate compact summary in diffstat
    --binary              output a binary diff that can be applied
    --[no-]full-index     show full pre- and post-image object names on the "index" lines
    --[no-]color[=<when>] show colored diff
    --ws-error-highlight <kind>
                          highlight whitespace errors in the 'context', 'old' or 'new' lines in the diff
    -z                    do not munge pathnames and use NULs as output field terminators in --raw or --numstat
    --[no-]abbrev[=<n>]   use <n> digits to display object names
    --src-prefix <prefix> show the given source prefix instead of "a/"
    --dst-prefix <prefix> show the given destination prefix instead of "b/"
    --line-prefix <prefix>
                          prepend an additional prefix to every line of output
    --no-prefix           do not show any source or destination prefix
    --default-prefix      use default prefixes a/ and b/
    --inter-hunk-context <n>
                          show context between diff hunks up to the specified number of lines
    --output-indicator-new <char>
                          specify the character to indicate a new line instead of '+'
    --output-indicator-old <char>
                          specify the character to indicate an old line instead of '-'
    --output-indicator-context <char>
                          specify the character to indicate a context instead of ' '

Diff rename options
    -B, --break-rewrites[=<n>[/<m>]]
                          break complete rewrite changes into pairs of delete and create
    -M, --find-renames[=<n>]
                          detect renames
    -D, --irreversible-delete
                          omit the preimage for deletes
    -C, --find-copies[=<n>]
                          detect copies
    --[no-]find-copies-harder
                          use unmodified files as source to find copies
    --no-renames          disable rename detection
    --[no-]rename-empty   use empty blobs as rename source
    --[no-]follow         continue listing the history of a file beyond renames
    -l <n>                prevent rename/copy detection if the number of rename/copy targets exceeds given limit

Diff algorithm options
    --minimal             produce the smallest possible diff
    -w, --ignore-all-space
                          ignore whitespace when comparing lines
    -b, --ignore-space-change
                          ignore changes in amount of whitespace
    --ignore-space-at-eol ignore changes in whitespace at EOL
    --ignore-cr-at-eol    ignore carrier-return at the end of line
    --ignore-blank-lines  ignore changes whose lines are all blank
    -I, --[no-]ignore-matching-lines <regex>
                          ignore changes whose all lines match <regex>
    --[no-]indent-heuristic
                          heuristic to shift diff hunk boundaries for easy reading
    --patience            generate diff using the "patience diff" algorithm
    --histogram           generate diff using the "histogram diff" algorithm
    --diff-algorithm <algorithm>
                          choose a diff algorithm
    --anchored <text>     generate diff using the "anchored diff" algorithm
    --word-diff[=<mode>]  show word diff, using <mode> to delimit changed words
    --word-diff-regex <regex>
                          use <regex> to decide what a word is
    --color-words[=<regex>]
                          equivalent to --word-diff=color --word-diff-regex=<regex>
    --[no-]color-moved[=<mode>]
                          moved lines of code are colored differently
    --[no-]color-moved-ws <mode>
                          how white spaces are ignored in --color-moved

Other diff options
    --[no-]relative[=<prefix>]
                          when run from subdir, exclude changes outside and show relative paths
    -a, --[no-]text       treat all files as text
    -R                    swap two inputs, reverse the diff
    --[no-]exit-code      exit with 1 if there were differences, 0 otherwise
    --[no-]quiet          disable all output of the program
    --[no-]ext-diff       allow an external diff helper to be executed
    --[no-]textconv       run external text conversion filters when comparing binary files
    --ignore-submodules[=<when>]
                          ignore changes to submodules in the diff generation
    --submodule[=<format>]
                          specify how differences in submodules are shown
    --ita-invisible-in-index
                          hide 'git add -N' entries from the index
    --ita-visible-in-index
                          treat 'git add -N' entries as real in the index
    -S <string>           look for differences that change the number of occurrences of the specified string
    -G <regex>            look for differences that change the number of occurrences of the specified regex
    --pickaxe-all         show all changes in the changeset with -S or -G
    --pickaxe-regex       treat <string> in -S as extended POSIX regular expression
    -O <file>             control the order in which files appear in the output
    --rotate-to <path>    show the change in the specified path first
    --skip-to <path>      skip the output to the specified path
    --find-object <object-id>
                          look for differences that change the number of occurrences of the specified object
    --diff-filter [(A|C|D|M|R|T|U|X|B)...[*]]
                          select files by diff type
    --max-depth <depth>   maximum tree depth to recurse
    --output <file>       output to a specific file
```

### `git diff --name-status`
- ????: `129`

```text
warning: Not a git repository. Use --no-index to compare two paths outside a working tree
usage: git diff --no-index [<options>] <path> <path> [<pathspec>...]

Diff output format options
    -p, --patch           generate patch
    -s, --no-patch        suppress diff output
    -u                    generate patch
    -U, --unified[=<n>]   generate diffs with <n> lines context
    -W, --[no-]function-context
                          generate diffs with <n> lines context
    --raw                 generate the diff in raw format
    --patch-with-raw      synonym for '-p --raw'
    --patch-with-stat     synonym for '-p --stat'
    --numstat             machine friendly --stat
    --shortstat           output only the last line of --stat
    -X, --dirstat[=<param1>,<param2>...]
                          output the distribution of relative amount of changes for each sub-directory
    --cumulative          synonym for --dirstat=cumulative
    --dirstat-by-file[=<param1>,<param2>...]
                          synonym for --dirstat=files,<param1>,<param2>...
    --check               warn if changes introduce conflict markers or whitespace errors
    --summary             condensed summary such as creations, renames and mode changes
    --name-only           show only names of changed files
    --name-status         show only names and status of changed files
    --stat[=<width>[,<name-width>[,<count>]]]
                          generate diffstat
    --stat-width <width>  generate diffstat with a given width
    --stat-name-width <width>
                          generate diffstat with a given name width
    --stat-graph-width <width>
                          generate diffstat with a given graph width
    --stat-count <count>  generate diffstat with limited lines
    --[no-]compact-summary
                          generate compact summary in diffstat
    --binary              output a binary diff that can be applied
    --[no-]full-index     show full pre- and post-image object names on the "index" lines
    --[no-]color[=<when>] show colored diff
    --ws-error-highlight <kind>
                          highlight whitespace errors in the 'context', 'old' or 'new' lines in the diff
    -z                    do not munge pathnames and use NULs as output field terminators in --raw or --numstat
    --[no-]abbrev[=<n>]   use <n> digits to display object names
    --src-prefix <prefix> show the given source prefix instead of "a/"
    --dst-prefix <prefix> show the given destination prefix instead of "b/"
    --line-prefix <prefix>
                          prepend an additional prefix to every line of output
    --no-prefix           do not show any source or destination prefix
    --default-prefix      use default prefixes a/ and b/
    --inter-hunk-context <n>
                          show context between diff hunks up to the specified number of lines
    --output-indicator-new <char>
                          specify the character to indicate a new line instead of '+'
    --output-indicator-old <char>
                          specify the character to indicate an old line instead of '-'
    --output-indicator-context <char>
                          specify the character to indicate a context instead of ' '

Diff rename options
    -B, --break-rewrites[=<n>[/<m>]]
                          break complete rewrite changes into pairs of delete and create
    -M, --find-renames[=<n>]
                          detect renames
    -D, --irreversible-delete
                          omit the preimage for deletes
    -C, --find-copies[=<n>]
                          detect copies
    --[no-]find-copies-harder
                          use unmodified files as source to find copies
    --no-renames          disable rename detection
    --[no-]rename-empty   use empty blobs as rename source
    --[no-]follow         continue listing the history of a file beyond renames
    -l <n>                prevent rename/copy detection if the number of rename/copy targets exceeds given limit

Diff algorithm options
    --minimal             produce the smallest possible diff
    -w, --ignore-all-space
                          ignore whitespace when comparing lines
    -b, --ignore-space-change
                          ignore changes in amount of whitespace
    --ignore-space-at-eol ignore changes in whitespace at EOL
    --ignore-cr-at-eol    ignore carrier-return at the end of line
    --ignore-blank-lines  ignore changes whose lines are all blank
    -I, --[no-]ignore-matching-lines <regex>
                          ignore changes whose all lines match <regex>
    --[no-]indent-heuristic
                          heuristic to shift diff hunk boundaries for easy reading
    --patience            generate diff using the "patience diff" algorithm
    --histogram           generate diff using the "histogram diff" algorithm
    --diff-algorithm <algorithm>
                          choose a diff algorithm
    --anchored <text>     generate diff using the "anchored diff" algorithm
    --word-diff[=<mode>]  show word diff, using <mode> to delimit changed words
    --word-diff-regex <regex>
                          use <regex> to decide what a word is
    --color-words[=<regex>]
                          equivalent to --word-diff=color --word-diff-regex=<regex>
    --[no-]color-moved[=<mode>]
                          moved lines of code are colored differently
    --[no-]color-moved-ws <mode>
                          how white spaces are ignored in --color-moved

Other diff options
    --[no-]relative[=<prefix>]
                          when run from subdir, exclude changes outside and show relative paths
    -a, --[no-]text       treat all files as text
    -R                    swap two inputs, reverse the diff
    --[no-]exit-code      exit with 1 if there were differences, 0 otherwise
    --[no-]quiet          disable all output of the program
    --[no-]ext-diff       allow an external diff helper to be executed
    --[no-]textconv       run external text conversion filters when comparing binary files
    --ignore-submodules[=<when>]
                          ignore changes to submodules in the diff generation
    --submodule[=<format>]
                          specify how differences in submodules are shown
    --ita-invisible-in-index
                          hide 'git add -N' entries from the index
    --ita-visible-in-index
                          treat 'git add -N' entries as real in the index
    -S <string>           look for differences that change the number of occurrences of the specified string
    -G <regex>            look for differences that change the number of occurrences of the specified regex
    --pickaxe-all         show all changes in the changeset with -S or -G
    --pickaxe-regex       treat <string> in -S as extended POSIX regular expression
    -O <file>             control the order in which files appear in the output
    --rotate-to <path>    show the change in the specified path first
    --skip-to <path>      skip the output to the specified path
    --find-object <object-id>
                          look for differences that change the number of occurrences of the specified object
    --diff-filter [(A|C|D|M|R|T|U|X|B)...[*]]
                          select files by diff type
    --max-depth <depth>   maximum tree depth to recurse
    --output <file>       output to a specific file
```

## 3. src ?? ?? ?? (node_modules, dist, .git ??)

```text
src/api/.gitkeep
src/app/AppShell.tsx
src/App.tsx
src/components/common/.gitkeep
src/components/common/EmptyState.tsx
src/components/common/PageHeader.tsx
src/components/common/SectionCard.tsx
src/components/common/StatCard.tsx
src/components/common/StatusBadge.tsx
src/components/dashboard/.gitkeep
src/components/layout/.gitkeep
src/components/reports/.gitkeep
src/components/risk/.gitkeep
src/components/stocks/.gitkeep
src/data/json/codes.json
src/data/json/sampleSchemaComments.json
src/data/json/sampleStocks.json
src/data/json/sampleWatchlist.json
src/data/json/sideMenus.json
src/data/json/topMenus.json
src/index.css
src/layouts/AdminLayout.tsx
src/main.tsx
src/pages/.gitkeep
src/pages/ClassificationRulesPage.tsx
src/pages/CollectionRunsPage.tsx
src/pages/DashboardPage.tsx
src/pages/DisclosuresPage.tsx
src/pages/NewsPage.tsx
src/pages/SchemaCommentsPage.tsx
src/pages/StocksPage.tsx
src/pages/WatchlistPage.tsx
src/router/AppRouter.tsx
src/router/routeRegistry.tsx
src/services/api/apiClient.ts
src/services/api/classificationRuleApiRepository.ts
src/services/api/collectionRunApiRepository.ts
src/services/api/disclosureApiRepository.ts
src/services/api/newsApiRepository.ts
src/services/api/schemaCommentApiRepository.ts
src/services/api/stockApiRepository.ts
src/services/api/watchlistApiRepository.ts
src/services/config/appConfig.ts
src/services/index.ts
src/services/mock/classificationRuleMockRepository.ts
src/services/mock/collectionRunMockRepository.ts
src/services/mock/disclosureMockRepository.ts
src/services/mock/newsMockRepository.ts
src/services/mock/schemaCommentMockRepository.ts
src/services/mock/stockMockRepository.ts
src/services/mock/watchlistMockRepository.ts
src/types/.gitkeep
src/types/classificationRule.ts
src/types/collectionRun.ts
src/types/disclosure.ts
src/types/news.ts
src/types/schemaComment.ts
src/types/stock.ts
src/types/watchlist.ts
src/utils/format.ts
```

## 4. ?? ?? ?? ?? ??

### `D:/12. Automation/Codex/01. DrCT에셋/drct-asset-office/package.json`

```json
[MISSING] D:\12. Automation\Codex\01. DrCT에셋\drct-asset-office\package.json
```

### `frontend/package.json`

```json
{
  "name": "drct-asset-office-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1 --port 5173",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1 --port 5173"
  },
  "dependencies": {
    "clsx": "^2.1.1",
    "lucide-react": "^0.525.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.30.1"
  },
  "devDependencies": {
    "@types/node": "^22.10.2",
    "@types/react": "^18.3.8",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.14",
    "typescript": "^5.6.2",
    "vite": "^5.4.8"
  }
}

```

### `frontend/src/main.tsx`

```tsx
﻿import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>
);

```

### `frontend/src/App.tsx`

```tsx
﻿import AppShell from "@/app/AppShell";

function App() {
  return <AppShell />;
}

export default App;

```

### `frontend/src/index.css`

```css
﻿@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --color-primary: #150f23;
  --color-ink-deep: #1f1633;
  --color-surface-dark: #1f1633;
  --color-surface-night: #150f23;
  --color-canvas-dark: #1f1633;
  --color-canvas-light: #ffffff;
  --color-surface-soft: #f7f7fb;

  --color-accent-lime: #c2ef4e;
  --color-accent-pink: #fa7faa;
  --color-accent-violet: #6a5fc1;
  --color-accent-violet-deep: #422082;
  --color-accent-violet-mid: #79628c;

  --color-on-primary: #ffffff;
  --color-ink: #1f1633;
  --color-muted-dark: rgba(255, 255, 255, 0.72);
  --color-faint-dark: rgba(255, 255, 255, 0.18);
  --color-muted-light: #6b7280;

  --color-hairline-violet: #362d59;
  --color-hairline-cloud: #e5e7eb;
  --color-hairline-cool: #cfcfdb;

  --color-danger: #ef4444;
  --color-warning: #f59e0b;
  --color-success: #22c55e;
  --color-focus-ring: rgba(59, 130, 246, 0.5);

  --space-xxs: 2px;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-xxl: 32px;
  --space-section: 96px;

  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  --radius-xxl: 18px;
  --radius-full: 9999px;

  color-scheme: light;
}

body {
  margin: 0;
  font-family: Rubik, Pretendard, "Noto Sans KR", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--color-ink);
  background: var(--color-canvas-light);
}

* {
  box-sizing: border-box;
}

input,
select,
textarea,
button {
  font: inherit;
}

button:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible,
a:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--color-focus-ring);
}

.app-shell {
  min-height: 100vh;
  background: var(--color-canvas-light);
  color: var(--color-ink);
}

.app-shell-dark {
  color: var(--color-on-primary);
  background:
    radial-gradient(circle at top left, rgba(194, 239, 78, 0.08), transparent 28%),
    radial-gradient(circle at top right, rgba(250, 127, 170, 0.08), transparent 24%),
    var(--color-canvas-dark);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-xl);
  margin-bottom: var(--space-lg);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-hairline-cloud);
  padding: var(--space-xl);
  background: var(--color-canvas-light);
}

.page-header-dark {
  border-color: var(--color-hairline-violet);
  background: rgba(21, 15, 35, 0.9);
}

.page-title {
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
  font-weight: 600;
}

.page-description {
  margin: var(--space-sm) 0 0;
  color: var(--color-muted-light);
  font-size: 14px;
  line-height: 1.5;
}

.page-header-dark .page-description {
  color: var(--color-muted-dark);
}

.keyword-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  border-radius: var(--radius-xs);
  padding: 0 var(--space-md);
  min-height: 28px;
  color: var(--color-ink-deep);
  background: var(--color-accent-lime);
  font-size: 12px;
  font-weight: 700;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: var(--space-md) var(--space-lg);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.14;
  letter-spacing: 0.2px;
  cursor: pointer;
  transition: all 0.18s ease;
  text-decoration: none;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-primary {
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.app-shell-dark .btn-primary {
  color: var(--color-ink-deep);
  background: var(--color-on-primary);
}

.btn-secondary {
  color: var(--color-ink-deep);
  background: var(--color-surface-soft);
  border-color: var(--color-hairline-cloud);
}

.app-shell-dark .btn-secondary {
  color: var(--color-on-primary);
  background: var(--color-faint-dark);
  border-color: var(--color-hairline-violet);
}

.btn-danger {
  color: #fff;
  background: var(--color-danger);
}

.btn-link {
  color: var(--color-accent-violet);
  background: transparent;
  border-color: var(--color-hairline-cool);
}

.btn-on-light {
  color: var(--color-ink-deep) !important;
  background: var(--color-surface-soft) !important;
  border-color: var(--color-hairline-cloud) !important;
}

.card {
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-hairline-cloud);
  padding: var(--space-xl);
  background: var(--color-canvas-light);
}

.card-dark {
  color: var(--color-on-primary);
  background: var(--color-surface-night);
  border-color: var(--color-hairline-violet);
}

.section-title {
  margin: 0 0 var(--space-lg);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.text-muted {
  color: var(--color-muted-light);
}

.card-dark .text-muted {
  color: var(--color-muted-dark);
}

.input-control,
.select-control,
.textarea-control {
  width: 100%;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-hairline-cool);
  background: #fff;
  color: var(--color-ink);
  min-height: 44px;
  padding: var(--space-md) var(--space-md);
}

.textarea-control {
  min-height: 96px;
  resize: vertical;
}

.card-dark .input-control,
.card-dark .select-control,
.card-dark .textarea-control {
  border-color: var(--color-hairline-violet);
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-on-primary);
}

.table-shell {
  overflow: auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-hairline-cloud);
  background: #fff;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table th,
.data-table td {
  min-height: 44px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-hairline-cloud);
  text-align: left;
  vertical-align: middle;
}

.data-table th {
  color: var(--color-muted-light);
  font-weight: 600;
  background: var(--color-surface-soft);
}

.data-table tbody tr:nth-child(odd) {
  background: #fff;
}

.data-table tbody tr:nth-child(even) {
  background: #fafafe;
}

.data-table tbody tr:hover {
  background: #f1f5f9;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  min-height: 24px;
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-xs);
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.badge-slate {
  color: #475569;
  border-color: #cbd5e1;
  background: #f1f5f9;
}

.badge-blue {
  color: #1e3a8a;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.badge-emerald,
.badge-positive {
  color: #065f46;
  border-color: #a7f3d0;
  background: #ecfdf5;
}

.badge-amber,
.badge-importance-medium,
.badge-risk-medium {
  color: #92400e;
  border-color: #fcd34d;
  background: #fffbeb;
}

.badge-rose,
.badge-negative,
.badge-risk-high {
  color: #9f1239;
  border-color: #fecdd3;
  background: #fff1f2;
}

.badge-neutral,
.badge-importance-low,
.badge-risk-unknown {
  color: #6b7280;
  border-color: #e5e7eb;
  background: #f3f4f6;
}

.badge-importance-high,
.badge-risk-low,
.badge-event {
  color: #1f1633;
  border-color: #c2ef4e;
  background: #f4ffda;
}

.empty-state {
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-hairline-cool);
  background: #f8fafc;
  padding: 32px;
  text-align: center;
  font-size: 14px;
  color: var(--color-muted-light);
}

.hero-panel {
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-hairline-violet);
  padding: var(--space-xxl);
  background:
    radial-gradient(circle at 80% 0, rgba(194, 239, 78, 0.13), transparent 34%),
    linear-gradient(130deg, #1f1633 0%, #150f23 64%);
  color: var(--color-on-primary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: var(--space-lg);
}

@media (min-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

```

## 5. ???? ?? ?? ?? ??

### `frontend/src/app/AppShell.tsx`

```tsx
﻿import AppRouter from "@/router/AppRouter";

function AppShell() {
  return <AppRouter />;
}

export default AppShell;

```

### `frontend/src/components/common/PageHeader.tsx`

```tsx
﻿import type { ReactNode } from "react";
import clsx from "clsx";

type Props = {
  title: string;
  description?: string;
  action?: ReactNode;
  theme?: "light" | "dark";
};

function PageHeader({ title, description, action, theme = "light" }: Props) {
  return (
    <div className={clsx("page-header", theme === "dark" && "page-header-dark")}>
      <div>
        <h2 className="page-title">{title}</h2>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export default PageHeader;

```

### `frontend/src/components/layout/.gitkeep`

```text

```

### `frontend/src/data/json/sideMenus.json`

```json
﻿[
  { "menuKey": "investment", "title": "대시보드", "routeKey": "dashboard" },
  { "menuKey": "investment", "title": "종목 관리", "routeKey": "stocks" },
  { "menuKey": "investment", "title": "관심종목 관리", "routeKey": "watchlist" },
  { "menuKey": "data", "title": "스키마 코멘트", "routeKey": "schema-comments" },
  { "menuKey": "data", "title": "뉴스 관리", "routeKey": "news" },
  { "menuKey": "data", "title": "공시 관리", "routeKey": "disclosures" },
  { "menuKey": "data", "title": "수집 이력", "routeKey": "collection-runs" },
  { "menuKey": "data", "title": "분류 규칙 관리", "routeKey": "classification-rules" },
  { "menuKey": "system", "title": "설정", "routeKey": "settings" }
]

```

### `frontend/src/data/json/topMenus.json`

```json
[
  { "menuKey": "investment", "title": "\ud22c\uc790\uad00\ub9ac" },
  { "menuKey": "data", "title": "\ub370\uc774\ud130\uad00\ub9ac" },
  { "menuKey": "system", "title": "\uc2dc\uc2a4\ud15c" }
]

```

### `frontend/src/layouts/AdminLayout.tsx`

```tsx
﻿import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Building2, Database, LayoutDashboard, Settings, Star } from "lucide-react";
import clsx from "clsx";
import topMenus from "@/data/json/topMenus.json";
import sideMenus from "@/data/json/sideMenus.json";
import { routeRegistryMap } from "@/router/routeRegistry";
import { dataSourceLabel } from "@/services";
import { appConfig } from "@/services/config/appConfig";
import StatusBadge from "@/components/common/StatusBadge";

const iconMap = {
  dashboard: LayoutDashboard,
  stocks: Building2,
  watchlist: Star,
  "schema-comments": Database,
  settings: Settings,
} as const;

const darkAnalysisRoutes = new Set(["/dashboard", "/news", "/disclosures"]);

function AdminLayout() {
  const location = useLocation();
  const [apiStatus, setApiStatus] = useState<"확인중" | "정상" | "오프라인">("확인중");

  useEffect(() => {
    const run = async () => {
      if (dataSourceLabel !== "api") {
        setApiStatus("정상");
        return;
      }
      try {
        const res = await fetch(`${appConfig.apiBaseUrl}/health`);
        setApiStatus(res.ok ? "정상" : "오프라인");
      } catch {
        setApiStatus("오프라인");
      }
    };
    run();
  }, []);

  const activeTopMenuKey = useMemo(() => {
    const found = sideMenus.find((m) => {
      const route = routeRegistryMap[m.routeKey];
      return route && location.pathname === route.path;
    });
    return found?.menuKey ?? "investment";
  }, [location.pathname]);

  const grouped = useMemo(() => {
    return topMenus.map((top) => ({
      ...top,
      items: sideMenus.filter((s) => s.menuKey === top.menuKey),
    }));
  }, []);

  const isDarkPage = darkAnalysisRoutes.has(location.pathname);

  return (
    <div className={clsx("app-shell", isDarkPage && "app-shell-dark")}>
      <header
        className={clsx(
          "sticky top-0 z-20 border-b backdrop-blur",
          isDarkPage ? "border-[var(--color-hairline-violet)] bg-[#1a1330]/92" : "border-slate-200 bg-white/95",
        )}
      >
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <p className={clsx("text-lg font-semibold", isDarkPage ? "text-white" : "text-[var(--color-ink)]")}>DrCT에셋</p>
            <p className={clsx("text-xs", isDarkPage ? "text-white/70" : "text-slate-500")}>AI Investment Research Office</p>
          </div>

          <nav className="flex flex-wrap gap-2">
            {topMenus.map((menu) => (
              <span
                key={menu.menuKey}
                className={clsx(
                  "rounded-full border px-3 py-1.5 text-xs font-medium",
                  activeTopMenuKey === menu.menuKey
                    ? isDarkPage
                      ? "border-[var(--color-accent-lime)] bg-[rgba(194,239,78,0.18)] text-[var(--color-accent-lime)]"
                      : "border-[var(--color-accent-violet)] bg-[rgba(106,95,193,0.12)] text-[var(--color-ink)]"
                    : isDarkPage
                      ? "border-[var(--color-hairline-violet)] bg-[rgba(255,255,255,0.04)] text-white/70"
                      : "border-slate-200 bg-white text-slate-600",
                )}
              >
                {menu.title}
              </span>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone={dataSourceLabel === "api" ? "blue" : "slate"} />
            <StatusBadge label={`API: ${apiStatus}`} tone={apiStatus === "정상" ? "emerald" : apiStatus === "오프라인" ? "rose" : "amber"} />
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1500px] grid-cols-12 gap-6 px-6 py-6">
        <aside
          className={clsx(
            "col-span-12 rounded-2xl border p-4 md:col-span-3 lg:col-span-2",
            isDarkPage
              ? "border-[var(--color-hairline-violet)] bg-[rgba(21,15,35,0.78)]"
              : "border-slate-200 bg-white shadow-soft",
          )}
        >
          <div className="space-y-5">
            {grouped.map((group) => (
              <div key={group.menuKey}>
                <p className={clsx("mb-2 px-2 text-[11px] font-semibold uppercase tracking-wide", isDarkPage ? "text-white/45" : "text-slate-400")}>{group.title}</p>
                <ul className="space-y-1.5">
                  {group.items.map((menu) => {
                    const route = routeRegistryMap[menu.routeKey];
                    if (!route) return null;
                    const Icon = iconMap[menu.routeKey as keyof typeof iconMap] ?? LayoutDashboard;
                    return (
                      <li key={menu.routeKey}>
                        <NavLink
                          to={route.path}
                          className={({ isActive }) =>
                            clsx(
                              "relative flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition",
                              isActive
                                ? isDarkPage
                                  ? "bg-[rgba(194,239,78,0.12)] text-[var(--color-accent-lime)]"
                                  : "bg-brand-50 text-brand-900"
                                : isDarkPage
                                  ? "text-white/78 hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
                                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                            )
                          }
                        >
                          {({ isActive }) => (
                            <>
                              {isActive ? (
                                <span className={clsx("absolute left-0 top-2 h-6 w-1 rounded-r", isDarkPage ? "bg-[var(--color-accent-lime)]" : "bg-brand-600")} />
                              ) : null}
                              <Icon size={16} />
                              <span>{menu.title}</span>
                            </>
                          )}
                        </NavLink>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </aside>

        <section className="col-span-12 space-y-4 md:col-span-9 lg:col-span-10">
          <Outlet />
        </section>
      </main>
    </div>
  );
}

export default AdminLayout;

```

## 6. ?? ??? ?? ?? ??

### ????
- ??: `frontend/src/pages/DashboardPage.tsx`

```tsx
﻿import { Activity, BookOpenText, Briefcase, Database, FileText, Newspaper } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatCard from "@/components/common/StatCard";
import StatusBadge from "@/components/common/StatusBadge";
import { useEffect, useMemo, useState } from "react";
import { dataSourceLabel, repositories } from "@/services";

function DashboardPage() {
  const [stockCount, setStockCount] = useState(0);
  const [watchlistCount, setWatchlistCount] = useState(0);
  const [schemaCount, setSchemaCount] = useState(0);
  const [health, setHealth] = useState("확인중");

  useEffect(() => {
    const run = async () => {
      try {
        const [stocks, watchlist, comments] = await Promise.all([
          repositories.stocks.list(),
          repositories.watchlist.list(),
          repositories.schemaComments.list(),
        ]);
        setStockCount(stocks.length);
        setWatchlistCount(watchlist.length);
        setSchemaCount(comments.length);
        setHealth("정상");
      } catch {
        setHealth("연결 실패");
      }
    };
    run();
  }, []);

  const stats = useMemo(
    () => [
      { title: "API 연결 상태", value: health, icon: Activity },
      { title: "종목 수", value: `${stockCount}`, icon: Briefcase },
      { title: "관심종목 수", value: `${watchlistCount}`, icon: BookOpenText },
      { title: "Schema Comment 수", value: `${schemaCount}`, icon: Database },
    ],
    [health, schemaCount, stockCount, watchlistCount],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        theme="dark"
        title="대시보드"
        description="오늘의 투자 판단 근거를 정리하고, 수집·분석 흐름 상태를 확인합니다."
        action={<span className="keyword-chip">AI 분석 콘솔</span>}
      />

      <SectionCard theme="dark">
        <div className="hero-panel">
          <p className="text-xs uppercase tracking-wider text-white/70">DrCT에셋</p>
          <h3 className="mt-2 text-2xl font-semibold">AI 기반 투자 근거 운영실</h3>
          <p className="mt-2 text-sm text-white/72">자동 판단이 아닌, 뉴스·공시·데이터 근거를 정리해 최종 검토를 돕습니다.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone="blue" />
            <StatusBadge label={`종목 ${stockCount}건`} tone="emerald" />
            <StatusBadge label={`관심종목 ${watchlistCount}건`} tone="amber" />
          </div>
        </div>
      </SectionCard>

      <div className="stats-grid">
        {stats.map((stat) => (
          <StatCard key={stat.title} title={stat.title} value={stat.value} icon={stat.icon} theme="dark" />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <StatCard title="뉴스/공시 수집" value="준비중" icon={Newspaper} description="수집 파이프라인 연동 예정" badge="Roadmap" theme="dark" />
        <StatCard title="리포트/GPT 자문" value="준비중" icon={FileText} description="리서치 자동화 연동 예정" badge="Roadmap" theme="dark" />
      </div>
    </div>
  );
}

export default DashboardPage;

```

### ?? ??
- ??: `frontend/src/pages/CollectionRunsPage.tsx`

```tsx
﻿import { RotateCw, Search } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { CollectionRun } from "@/types/collectionRun";
import { truncateText } from "@/utils/format";

const statusLabel: Record<string, string> = {
  running: "진행중",
  success: "성공",
  failed: "실패",
  partial: "부분성공",
};

const statusTone: Record<string, "slate" | "emerald" | "rose" | "amber" | "blue"> = {
  running: "blue",
  success: "emerald",
  failed: "rose",
  partial: "amber",
};

const statusOptions = [
  { value: "running", label: "진행중" },
  { value: "success", label: "성공" },
  { value: "failed", label: "실패" },
  { value: "partial", label: "부분성공" },
];

const initialFilters = {
  collectorName: "",
  status: "",
  target: "",
  limit: "50",
  offset: "0",
};

function CollectionRunsPage() {
  const [items, setItems] = useState<CollectionRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<CollectionRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [collectorName, setCollectorName] = useState(initialFilters.collectorName);
  const [status, setStatus] = useState(initialFilters.status);
  const [target, setTarget] = useState(initialFilters.target);
  const [limit, setLimit] = useState(initialFilters.limit);
  const [offset, setOffset] = useState(initialFilters.offset);

  const load = async (params?: { collectorName?: string; status?: string; target?: string; limit?: string; offset?: string }) => {
    const activeCollector = params?.collectorName ?? collectorName;
    const activeStatus = params?.status ?? status;
    const activeTarget = params?.target ?? target;
    const activeLimit = params?.limit ?? limit;
    const activeOffset = params?.offset ?? offset;

    setLoading(true);
    setError("");
    try {
      const data = await repositories.collectionRuns.listCollectionRuns({
        collector_name: activeCollector || undefined,
        status: activeStatus || undefined,
        target: activeTarget || undefined,
        limit: Number(activeLimit) || 50,
        offset: Number(activeOffset) || 0,
      });
      setItems(data);
      if (selectedRun) {
        const updated = data.find((item) => item.id === selectedRun.id) ?? null;
        setSelectedRun(updated);
      }
    } catch {
      setError("수집 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const summary = useMemo(() => {
    const result = { total: items.length, success: 0, failed: 0, partial: 0, running: 0 };
    for (const item of items) {
      if (item.status === "success") result.success += 1;
      else if (item.status === "failed") result.failed += 1;
      else if (item.status === "partial") result.partial += 1;
      else if (item.status === "running") result.running += 1;
    }
    return result;
  }, [items]);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    await load();
  };

  const onRefresh = async () => {
    await load();
  };

  const onReset = async () => {
    setCollectorName(initialFilters.collectorName);
    setStatus(initialFilters.status);
    setTarget(initialFilters.target);
    setLimit(initialFilters.limit);
    setOffset(initialFilters.offset);
    setSelectedRun(null);
    await load({
      collectorName: initialFilters.collectorName,
      status: initialFilters.status,
      target: initialFilters.target,
      limit: initialFilters.limit,
      offset: initialFilters.offset,
    });
  };

  return (
    <div className="space-y-4">
      <PageHeader title="수집 이력 관리" description="뉴스, 공시, 가격 등 데이터 수집 작업의 실행 결과를 확인합니다." />

      <SectionCard title="검색">
        <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-7">
          <div className="relative md:col-span-2">
            <p className="mb-1 text-xs text-slate-600">수집기명</p>
            <Search size={16} className="absolute left-3 top-8 text-slate-400" />
            <input className="input-control pl-9" placeholder="collector_name" value={collectorName} onChange={(e) => setCollectorName(e.target.value)} />
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">상태</p>
            <select className="select-control" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">전체</option>
              {statusOptions.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">대상</p>
            <input className="input-control" placeholder="target" value={target} onChange={(e) => setTarget(e.target.value)} />
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">조회 건수</p>
            <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">시작 위치</p>
            <select className="select-control" value={offset} onChange={(e) => setOffset(e.target.value)}>
              <option value="0">0</option>
              <option value="20">20</option>
              <option value="50">50</option>
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button type="submit" className="btn btn-primary">검색</button>
            <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
            <button type="button" className="btn btn-secondary inline-flex items-center gap-1" onClick={onRefresh}>
              <RotateCw size={14} /> 새로고침
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard title="상태 요약">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          <div className="card"><p className="text-xs text-muted">전체</p><p className="text-lg font-semibold">{summary.total}</p></div>
          <div className="card"><p className="text-xs text-emerald-700">성공</p><p className="text-lg font-semibold text-emerald-800">{summary.success}</p></div>
          <div className="card"><p className="text-xs text-rose-700">실패</p><p className="text-lg font-semibold text-rose-800">{summary.failed}</p></div>
          <div className="card"><p className="text-xs text-amber-700">부분성공</p><p className="text-lg font-semibold text-amber-800">{summary.partial}</p></div>
          <div className="card"><p className="text-xs text-indigo-700">진행중</p><p className="text-lg font-semibold text-indigo-800">{summary.running}</p></div>
        </div>
      </SectionCard>

      <SectionCard title="수집 이력 목록">
        {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        {!loading && !error && items.length === 0 ? <EmptyState message="수집 이력이 없습니다." /> : null}

        {!loading && !error && items.length > 0 ? (
          <div className="table-shell">
            <table className="data-table min-w-[1200px]">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>수집기명</th>
                  <th>대상</th>
                  <th>상태</th>
                  <th>시작일시</th>
                  <th>종료일시</th>
                  <th>메시지</th>
                  <th>생성일시</th>
                  <th>상세</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td>{r.collector_name}</td>
                    <td>{r.target || "-"}</td>
                    <td><StatusBadge label={statusLabel[r.status] || r.status} tone={statusTone[r.status] || "slate"} /></td>
                    <td>{r.started_at}</td>
                    <td>{r.finished_at || "-"}</td>
                    <td>{truncateText(r.message, 80)}</td>
                    <td>{r.created_at}</td>
                    <td>
                      {r.message ? (
                        <button type="button" className="btn btn-secondary" onClick={() => setSelectedRun(r)}>
                          자세히
                        </button>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </SectionCard>

      {selectedRun ? (
        <SectionCard title="상세 메시지">
          <div className="space-y-1 text-sm">
            <p><span className="text-muted">ID:</span> {selectedRun.id}</p>
            <p><span className="text-muted">수집기명:</span> {selectedRun.collector_name}</p>
            <p><span className="text-muted">대상:</span> {selectedRun.target || "-"}</p>
            <p><span className="text-muted">상태:</span> {statusLabel[selectedRun.status] || selectedRun.status}</p>
            <p><span className="text-muted">시작일시:</span> {selectedRun.started_at}</p>
            <p><span className="text-muted">종료일시:</span> {selectedRun.finished_at || "-"}</p>
            <p><span className="text-muted">메시지:</span></p>
            <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-3 text-xs text-slate-700">{selectedRun.message || "-"}</pre>
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}

export default CollectionRunsPage;

```

### ???? ??
- ??: `frontend/src/pages/WatchlistPage.tsx`

```tsx
﻿import { FormEvent, useEffect, useState } from "react";
import codes from "@/data/json/codes.json";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { Stock } from "@/types/stock";
import type { Watchlist, WatchlistCreateInput, WatchlistUpdateInput } from "@/types/watchlist";

const statusToneMap: Record<string, "blue" | "slate" | "emerald" | "amber" | "rose"> = {
  관심: "blue",
  관망: "slate",
  매수후보: "emerald",
  보유중: "amber",
  제외: "rose",
};

function WatchlistPage() {
  const [items, setItems] = useState<Watchlist[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [form, setForm] = useState<WatchlistCreateInput>({ stock_id: 0, status: "관심" });

  const load = async () => {
    setItems(await repositories.watchlist.list({ keyword: keyword || undefined, status: status || undefined }));
  };

  useEffect(() => {
    const run = async () => {
      const [watch, stockList] = await Promise.all([repositories.watchlist.list(), repositories.stocks.list()]);
      setItems(watch);
      setStocks(stockList);
      if (stockList.length > 0) setForm((prev) => ({ ...prev, stock_id: stockList[0].id }));
    };
    run();
  }, []);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    await repositories.watchlist.create(form);
    await load();
  };

  const onUpdate = async (item: Watchlist, patch: WatchlistUpdateInput) => {
    await repositories.watchlist.update(item.id, patch);
    await load();
  };

  const onDelete = async (id: number) => {
    await repositories.watchlist.remove(id);
    await load();
  };

  return (
    <div className="space-y-4">
      <PageHeader title="관심종목 관리" description="투자 관찰 대상과 진입/제외 조건을 관리합니다." />

      <SectionCard title="필터">
        <div className="flex flex-wrap gap-2">
          <select className="select-control" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">전체 상태</option>
            {codes.watchlistStatus.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input className="input-control min-w-72 flex-1" placeholder="코드/종목명 검색" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <button className="btn btn-primary" onClick={load}>검색</button>
        </div>
      </SectionCard>

      <SectionCard title="관심종목 등록">
        <form onSubmit={onCreate} className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <select className="select-control" value={form.stock_id} onChange={(e) => setForm({ ...form, stock_id: Number(e.target.value) })}>
            {stocks.map((s) => <option key={s.id} value={s.id}>{s.stock_code} - {s.stock_name}</option>)}
          </select>
          <select className="select-control" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            {codes.watchlistStatus.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button type="submit" className="btn btn-primary">등록</button>
          <input className="input-control" placeholder="관심 사유" onChange={(e) => setForm({ ...form, interest_reason: e.target.value })} />
          <input className="input-control" placeholder="진입 조건" onChange={(e) => setForm({ ...form, entry_condition: e.target.value })} />
          <input className="input-control" placeholder="제외 조건" onChange={(e) => setForm({ ...form, exit_condition: e.target.value })} />
        </form>
      </SectionCard>

      <SectionCard title="관심종목 목록">
        {items.length === 0 ? (
          <EmptyState message="조회된 관심종목이 없습니다." />
        ) : (
          <div className="table-shell">
            <table className="data-table min-w-[1200px]">
              <thead>
                <tr>
                  <th>종목</th>
                  <th>상태</th>
                  <th>관심 사유</th>
                  <th>진입 조건</th>
                  <th>제외 조건</th>
                  <th>리스크 메모</th>
                  <th>작업</th>
                </tr>
              </thead>
              <tbody>
                {items.map((w) => (
                  <tr key={w.id}>
                    <td><p className="font-semibold text-slate-900">{w.stock_code}</p><p className="text-xs text-slate-500">{w.stock_name}</p></td>
                    <td><StatusBadge label={w.status} tone={statusToneMap[w.status] ?? "slate"} /></td>
                    <td>{w.interest_reason || "-"}</td>
                    <td>{w.entry_condition || "-"}</td>
                    <td>{w.exit_condition || "-"}</td>
                    <td>{w.risk_note || "-"}</td>
                    <td>
                      <div className="flex gap-2">
                        <button className="btn btn-secondary" onClick={() => onUpdate(w, { status: "관망" })}>상태수정</button>
                        <button className="btn btn-danger" onClick={() => onDelete(w.id)}>삭제</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

export default WatchlistPage;

```

### ?? ?? ??
- ??: `frontend/src/pages/ClassificationRulesPage.tsx`

```tsx
﻿import { FormEvent, useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { ClassificationRule, ClassificationRuleCreatePayload } from "@/types/classificationRule";

const defaultForm: ClassificationRuleCreatePayload = {
  target_type: "news",
  rule_group: "tag",
  rule_name: "",
  keywords: "",
  output_field: "ai_tags",
  output_value: "",
  score_delta: 0,
  priority: 100,
  is_active: true,
  description: "",
};

function ClassificationRulesPage() {
  const [items, setItems] = useState<ClassificationRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [targetType, setTargetType] = useState("");
  const [ruleGroup, setRuleGroup] = useState("");
  const [isActive, setIsActive] = useState("");
  const [keyword, setKeyword] = useState("");

  const [form, setForm] = useState<ClassificationRuleCreatePayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);

  const isEdit = useMemo(() => editingId !== null, [editingId]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await repositories.classificationRules.listClassificationRules({
        target_type: targetType || undefined,
        rule_group: ruleGroup || undefined,
        is_active: isActive === "" ? undefined : isActive === "true",
        keyword: keyword || undefined,
        limit: 100,
        offset: 0,
      });
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "분류 규칙을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    await load();
  };

  const onReset = async () => {
    setTargetType("");
    setRuleGroup("");
    setIsActive("");
    setKeyword("");
    setTimeout(() => {
      load();
    }, 0);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitLoading(true);
    setError("");
    try {
      if (isEdit && editingId !== null) {
        await repositories.classificationRules.updateClassificationRule(editingId, form);
      } else {
        await repositories.classificationRules.createClassificationRule(form);
      }
      setForm(defaultForm);
      setEditingId(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "규칙 저장 중 오류가 발생했습니다.");
    } finally {
      setSubmitLoading(false);
    }
  };

  const startEdit = (row: ClassificationRule) => {
    setEditingId(row.id);
    setForm({
      target_type: row.target_type,
      rule_group: row.rule_group,
      rule_name: row.rule_name,
      keywords: row.keywords,
      output_field: row.output_field,
      output_value: row.output_value,
      score_delta: row.score_delta,
      priority: row.priority,
      is_active: row.is_active,
      description: row.description ?? "",
    });
  };

  const onDeactivate = async (ruleId: number) => {
    try {
      await repositories.classificationRules.deactivateClassificationRule(ruleId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "규칙 비활성화 중 오류가 발생했습니다.");
    }
  };

  const onCancelEdit = () => {
    setEditingId(null);
    setForm(defaultForm);
  };

  return (
    <div className="space-y-4">
      <PageHeader title="분류 규칙 관리" description="뉴스와 공시의 태그·중요도·감성/리스크 분류 기준을 관리합니다." />

      <SectionCard title="검색/필터">
        <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
          <select className="select-control" value={targetType} onChange={(e) => setTargetType(e.target.value)}>
            <option value="">전체 대상</option>
            <option value="news">뉴스</option>
            <option value="disclosure">공시</option>
          </select>
          <select className="select-control" value={ruleGroup} onChange={(e) => setRuleGroup(e.target.value)}>
            <option value="">전체 그룹</option>
            <option value="tag">태그</option>
            <option value="sentiment">감성</option>
            <option value="importance">중요도</option>
            <option value="disclosure_event_type">공시 이벤트</option>
            <option value="disclosure_risk_level">공시 리스크</option>
          </select>
          <select className="select-control" value={isActive} onChange={(e) => setIsActive(e.target.value)}>
            <option value="">전체 상태</option>
            <option value="true">사용</option>
            <option value="false">미사용</option>
          </select>
          <input className="input-control" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <button type="submit" className="btn btn-primary">검색</button>
          <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
        </form>
      </SectionCard>

      <SectionCard title="규칙 등록/수정">
        <form onSubmit={onSubmit} className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <select className="select-control" value={form.target_type} onChange={(e) => setForm({ ...form, target_type: e.target.value })}>
            <option value="news">news</option>
            <option value="disclosure">disclosure</option>
          </select>
          <select className="select-control" value={form.rule_group} onChange={(e) => setForm({ ...form, rule_group: e.target.value })}>
            <option value="tag">tag</option>
            <option value="sentiment">sentiment</option>
            <option value="importance">importance</option>
            <option value="disclosure_event_type">disclosure_event_type</option>
            <option value="disclosure_risk_level">disclosure_risk_level</option>
          </select>
          <input className="input-control" placeholder="rule_name" value={form.rule_name} onChange={(e) => setForm({ ...form, rule_name: e.target.value })} required />
          <input className="input-control" placeholder="output_field" value={form.output_field} onChange={(e) => setForm({ ...form, output_field: e.target.value })} required />
          <textarea className="textarea-control md:col-span-2" placeholder="keywords (쉼표 구분)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} required />
          <input className="input-control" placeholder="output_value" value={form.output_value} onChange={(e) => setForm({ ...form, output_value: e.target.value })} required />
          <textarea className="textarea-control" placeholder="description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <input type="number" className="input-control" placeholder="score_delta" value={form.score_delta ?? 0} onChange={(e) => setForm({ ...form, score_delta: Number(e.target.value) })} />
          <input type="number" className="input-control" placeholder="priority" value={form.priority ?? 100} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
          <label className="flex items-center gap-2 rounded-xl border border-[var(--color-hairline-cool)] px-3 py-2 text-sm">
            <input type="checkbox" checked={Boolean(form.is_active)} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            is_active
          </label>
          <div className="flex gap-2 md:col-span-4">
            <button type="submit" className="btn btn-primary" disabled={submitLoading}>
              {isEdit ? "저장" : "신규 등록"}
            </button>
            {isEdit ? <button type="button" className="btn btn-secondary" onClick={onCancelEdit}>취소</button> : null}
          </div>
        </form>
      </SectionCard>

      <SectionCard title="규칙 목록">
        {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
        {!loading && !error && items.length === 0 ? <EmptyState message="분류 규칙이 없습니다." /> : null}

        {!loading && !error && items.length > 0 ? (
          <div className="table-shell">
            <table className="data-table min-w-[1550px]">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>대상</th>
                  <th>그룹</th>
                  <th>규칙명</th>
                  <th>키워드</th>
                  <th>출력 필드</th>
                  <th>출력 값</th>
                  <th>점수 가감</th>
                  <th>우선순위</th>
                  <th>사용 여부</th>
                  <th>설명</th>
                  <th>수정</th>
                  <th>비활성화</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.target_type}</td>
                    <td>{row.rule_group}</td>
                    <td>{row.rule_name}</td>
                    <td className="min-w-56">{row.keywords}</td>
                    <td>{row.output_field}</td>
                    <td>{row.output_value}</td>
                    <td>{row.score_delta}</td>
                    <td>{row.priority}</td>
                    <td>{row.is_active ? <StatusBadge label="사용" tone="emerald" /> : <StatusBadge label="미사용" tone="slate" />}</td>
                    <td>{row.description ?? "-"}</td>
                    <td><button type="button" className="btn btn-secondary" onClick={() => startEdit(row)}>수정</button></td>
                    <td>
                      {row.is_active ? (
                        <button type="button" className="btn btn-danger" onClick={() => onDeactivate(row.id)}>비활성화</button>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="안내">
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>keywords는 쉼표로 구분합니다.</li>
          <li>여러 키워드 중 하나라도 본문에 포함되면 규칙이 적용됩니다.</li>
          <li>priority가 낮을수록 먼저 적용됩니다.</li>
          <li>score_delta는 중요도 점수 보정값이며, is_active가 꺼져 있으면 적용되지 않습니다.</li>
        </ul>
      </SectionCard>
    </div>
  );
}

export default ClassificationRulesPage;

```

### ??
- ?? ??? ?? TSX ??? ?? ?????.

### ?? ?? ?? ??
- ?? ??? ?? `SettingsPage.tsx` ?? `frontend/src/router/routeRegistry.tsx`?? inline ????? ???? ????.

```tsx
﻿import ClassificationRulesPage from "@/pages/ClassificationRulesPage";
import CollectionRunsPage from "@/pages/CollectionRunsPage";
import DashboardPage from "@/pages/DashboardPage";
import DisclosuresPage from "@/pages/DisclosuresPage";
import NewsPage from "@/pages/NewsPage";
import SchemaCommentsPage from "@/pages/SchemaCommentsPage";
import StocksPage from "@/pages/StocksPage";
import WatchlistPage from "@/pages/WatchlistPage";

export type RouteItem = {
  routeKey: string;
  path: string;
  title: string;
  description: string;
  component: JSX.Element;
};

export const routeRegistry: RouteItem[] = [
  { routeKey: "dashboard", path: "/dashboard", title: "대시보드", description: "투자운영 현황 요약", component: <DashboardPage /> },
  { routeKey: "stocks", path: "/stocks", title: "종목 관리", description: "종목 등록/수정/비활성화", component: <StocksPage /> },
  { routeKey: "watchlist", path: "/watchlist", title: "관심종목 관리", description: "관심종목 등록/수정/삭제", component: <WatchlistPage /> },
  { routeKey: "schema-comments", path: "/schema-comments", title: "스키마 코멘트", description: "테이블/컬럼 한글 설명 데이터 사전", component: <SchemaCommentsPage /> },
  { routeKey: "news", path: "/news", title: "뉴스 관리", description: "수집된 종목 뉴스를 조회하고 검토합니다.", component: <NewsPage /> },
  { routeKey: "disclosures", path: "/disclosures", title: "공시 관리", description: "DART 공시 수집 결과를 조회하고 검토합니다.", component: <DisclosuresPage /> },
  { routeKey: "collection-runs", path: "/collection-runs", title: "수집 이력", description: "데이터 수집 실행 이력을 확인합니다.", component: <CollectionRunsPage /> },
  { routeKey: "classification-rules", path: "/classification-rules", title: "분류 규칙 관리", description: "뉴스와 공시의 태그·중요도·감성/리스크 분류 기준을 관리합니다.", component: <ClassificationRulesPage /> },
  { routeKey: "settings", path: "/settings", title: "설정", description: "시스템 설정 준비중", component: <div className="rounded-xl border border-slate-200 bg-white p-6">설정 화면 준비중입니다.</div> },
];

export const routeRegistryMap = Object.fromEntries(routeRegistry.map((route) => [route.routeKey, route]));

```

## 7. ?? UI ???? ?? ?? ??

### `frontend/src/components/common/PageHeader.tsx`

```tsx
﻿import type { ReactNode } from "react";
import clsx from "clsx";

type Props = {
  title: string;
  description?: string;
  action?: ReactNode;
  theme?: "light" | "dark";
};

function PageHeader({ title, description, action, theme = "light" }: Props) {
  return (
    <div className={clsx("page-header", theme === "dark" && "page-header-dark")}>
      <div>
        <h2 className="page-title">{title}</h2>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export default PageHeader;

```

### `frontend/src/components/common/SectionCard.tsx`

```tsx
﻿import type { ReactNode } from "react";
import clsx from "clsx";

type Props = {
  title?: string;
  children: ReactNode;
  theme?: "light" | "dark";
  className?: string;
};

function SectionCard({ title, children, theme = "light", className }: Props) {
  return (
    <section className={clsx("card", theme === "dark" && "card-dark", className)}>
      {title ? <h3 className="section-title">{title}</h3> : null}
      {children}
    </section>
  );
}

export default SectionCard;

```

### `frontend/src/components/common/StatCard.tsx`

```tsx
﻿import type { LucideIcon } from "lucide-react";
import clsx from "clsx";

type Props = {
  title: string;
  value: string;
  description?: string;
  icon: LucideIcon;
  badge?: string;
  theme?: "light" | "dark";
};

function StatCard({ title, value, description, icon: Icon, badge, theme = "light" }: Props) {
  return (
    <article className={clsx("card", theme === "dark" && "card-dark")}>
      <div className="flex items-start justify-between">
        <div className="rounded-xl border border-current/20 p-2 text-current">
          <Icon size={18} />
        </div>
        {badge ? <span className="badge badge-slate">{badge}</span> : null}
      </div>
      <p className="mt-4 text-sm text-muted">{title}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {description ? <p className="mt-1 text-xs text-muted">{description}</p> : null}
    </article>
  );
}

export default StatCard;

```

### `frontend/src/components/common/StatusBadge.tsx`

```tsx
﻿import clsx from "clsx";

type Tone = "emerald" | "amber" | "rose" | "blue" | "slate";
type Variant = "positive" | "neutral" | "negative" | "risk-high" | "risk-medium" | "risk-low" | "risk-unknown" | "importance-high" | "importance-medium" | "importance-low" | "event";

type Props = {
  label: string;
  tone?: Tone;
  variant?: Variant;
};

const toneMap: Record<Tone, string> = {
  emerald: "badge-emerald",
  amber: "badge-amber",
  rose: "badge-rose",
  blue: "badge-blue",
  slate: "badge-slate",
};

const variantMap: Record<Variant, string> = {
  positive: "badge-positive",
  neutral: "badge-neutral",
  negative: "badge-negative",
  "risk-high": "badge-risk-high",
  "risk-medium": "badge-risk-medium",
  "risk-low": "badge-risk-low",
  "risk-unknown": "badge-risk-unknown",
  "importance-high": "badge-importance-high",
  "importance-medium": "badge-importance-medium",
  "importance-low": "badge-importance-low",
  event: "badge-event",
};

function StatusBadge({ label, tone = "slate", variant }: Props) {
  return <span className={clsx("badge", variant ? variantMap[variant] : toneMap[tone])}>{label}</span>;
}

export default StatusBadge;

```

## 8. ??? ?? ?? ?? ??

### `app-shell`
- ?? ?? ?: `5`

- ??: `src/index.css` / ??: `82`
```text
0081: 
0082: .app-shell {
0083:   min-height: 100vh;
```

- ??: `src/index.css` / ??: `88`
```text
0087: 
0088: .app-shell-dark {
0089:   color: var(--color-on-primary);
```

- ??: `src/index.css` / ??: `172`
```text
0171: 
0172: .app-shell-dark .btn-primary {
0173:   color: var(--color-ink-deep);
```

- ??: `src/index.css` / ??: `183`
```text
0182: 
0183: .app-shell-dark .btn-secondary {
0184:   color: var(--color-on-primary);
```

- ??: `src/layouts/AdminLayout.tsx` / ??: `60`
```text
0059:   return (
0060:     <div className={clsx("app-shell", isDarkPage && "app-shell-dark")}>
0061:       <header
```

### `app-shell-dark`
- ?? ?? ?: `4`

- ??: `src/index.css` / ??: `88`
```text
0087: 
0088: .app-shell-dark {
0089:   color: var(--color-on-primary);
```

- ??: `src/index.css` / ??: `172`
```text
0171: 
0172: .app-shell-dark .btn-primary {
0173:   color: var(--color-ink-deep);
```

- ??: `src/index.css` / ??: `183`
```text
0182: 
0183: .app-shell-dark .btn-secondary {
0184:   color: var(--color-on-primary);
```

- ??: `src/layouts/AdminLayout.tsx` / ??: `60`
```text
0059:   return (
0060:     <div className={clsx("app-shell", isDarkPage && "app-shell-dark")}>
0061:       <header
```

### `page-header`
- ?? ?? ?: `4`

- ??: `src/components/common/PageHeader.tsx` / ??: `13`
```text
0012:   return (
0013:     <div className={clsx("page-header", theme === "dark" && "page-header-dark")}>
0014:       <div>
```

- ??: `src/index.css` / ??: `96`
```text
0095: 
0096: .page-header {
0097:   display: flex;
```

- ??: `src/index.css` / ??: `108`
```text
0107: 
0108: .page-header-dark {
0109:   border-color: var(--color-hairline-violet);
```

- ??: `src/index.css` / ??: `127`
```text
0126: 
0127: .page-header-dark .page-description {
0128:   color: var(--color-muted-dark);
```

### `page-header-dark`
- ?? ?? ?: `3`

- ??: `src/components/common/PageHeader.tsx` / ??: `13`
```text
0012:   return (
0013:     <div className={clsx("page-header", theme === "dark" && "page-header-dark")}>
0014:       <div>
```

- ??: `src/index.css` / ??: `108`
```text
0107: 
0108: .page-header-dark {
0109:   border-color: var(--color-hairline-violet);
```

- ??: `src/index.css` / ??: `127`
```text
0126: 
0127: .page-header-dark .page-description {
0128:   color: var(--color-muted-dark);
```

### `card`
- ?? ?? ?: `77`

- ??: `src/components/common/SectionCard.tsx` / ??: `11`
```text
0010: 
0011: function SectionCard({ title, children, theme = "light", className }: Props) {
0012:   return (
```

- ??: `src/components/common/SectionCard.tsx` / ??: `13`
```text
0012:   return (
0013:     <section className={clsx("card", theme === "dark" && "card-dark", className)}>
0014:       {title ? <h3 className="section-title">{title}</h3> : null}
```

- ??: `src/components/common/SectionCard.tsx` / ??: `20`
```text
0019: 
0020: export default SectionCard;
```

- ??: `src/components/common/StatCard.tsx` / ??: `13`
```text
0012: 
0013: function StatCard({ title, value, description, icon: Icon, badge, theme = "light" }: Props) {
0014:   return (
```

- ??: `src/components/common/StatCard.tsx` / ??: `15`
```text
0014:   return (
0015:     <article className={clsx("card", theme === "dark" && "card-dark")}>
0016:       <div className="flex items-start justify-between">
```

- ??: `src/components/common/StatCard.tsx` / ??: `29`
```text
0028: 
0029: export default StatCard;
```

- ??: `src/index.css` / ??: `206`
```text
0205: 
0206: .card {
0207:   border-radius: var(--radius-xl);
```

- ??: `src/index.css` / ??: `213`
```text
0212: 
0213: .card-dark {
0214:   color: var(--color-on-primary);
```

- ??: `src/index.css` / ??: `230`
```text
0229: 
0230: .card-dark .text-muted {
0231:   color: var(--color-muted-dark);
```

- ??: `src/index.css` / ??: `251`
```text
0250: 
0251: .card-dark .input-control,
0252: .card-dark .select-control,
```

- ??: `src/index.css` / ??: `252`
```text
0251: .card-dark .input-control,
0252: .card-dark .select-control,
0253: .card-dark .textarea-control {
```

- ??: `src/index.css` / ??: `253`
```text
0252: .card-dark .select-control,
0253: .card-dark .textarea-control {
0254:   border-color: var(--color-hairline-violet);
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `4`
```text
0003: import PageHeader from "@/components/common/PageHeader";
0004: import SectionCard from "@/components/common/SectionCard";
0005: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `131`
```text
0130: 
0131:       <SectionCard title="검색/필터">
0132:         <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `155`
```text
0154:         </form>
0155:       </SectionCard>
0156: 
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `157`
```text
0156: 
0157:       <SectionCard title="규칙 등록/수정">
0158:         <form onSubmit={onSubmit} className="grid grid-cols-1 gap-2 md:grid-cols-4">
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `188`
```text
0187:         </form>
0188:       </SectionCard>
0189: 
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `190`
```text
0189: 
0190:       <SectionCard title="규칙 목록">
0191:         {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `243`
```text
0242:         ) : null}
0243:       </SectionCard>
0244: 
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `245`
```text
0244: 
0245:       <SectionCard title="안내">
0246:         <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `252`
```text
0251:         </ul>
0252:       </SectionCard>
0253:     </div>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `5`
```text
0004: import PageHeader from "@/components/common/PageHeader";
0005: import SectionCard from "@/components/common/SectionCard";
0006: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `125`
```text
0124: 
0125:       <SectionCard title="검색">
0126:         <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-7">
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `169`
```text
0168:         </form>
0169:       </SectionCard>
0170: 
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `171`
```text
0170: 
0171:       <SectionCard title="상태 요약">
0172:         <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `173`
```text
0172:         <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
0173:           <div className="card"><p className="text-xs text-muted">전체</p><p className="text-lg font-semibold">{summary.total}</p></div>
0174:           <div className="card"><p className="text-xs text-emerald-700">성공</p><p className="text-lg font-semibold text-emerald-800">{summary.success}</p></div>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `174`
```text
0173:           <div className="card"><p className="text-xs text-muted">전체</p><p className="text-lg font-semibold">{summary.total}</p></div>
0174:           <div className="card"><p className="text-xs text-emerald-700">성공</p><p className="text-lg font-semibold text-emerald-800">{summary.success}</p></div>
0175:           <div className="card"><p className="text-xs text-rose-700">실패</p><p className="text-lg font-semibold text-rose-800">{summary.failed}</p></div>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `175`
```text
0174:           <div className="card"><p className="text-xs text-emerald-700">성공</p><p className="text-lg font-semibold text-emerald-800">{summary.success}</p></div>
0175:           <div className="card"><p className="text-xs text-rose-700">실패</p><p className="text-lg font-semibold text-rose-800">{summary.failed}</p></div>
0176:           <div className="card"><p className="text-xs text-amber-700">부분성공</p><p className="text-lg font-semibold text-amber-800">{summary.partial}</p></div>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `176`
```text
0175:           <div className="card"><p className="text-xs text-rose-700">실패</p><p className="text-lg font-semibold text-rose-800">{summary.failed}</p></div>
0176:           <div className="card"><p className="text-xs text-amber-700">부분성공</p><p className="text-lg font-semibold text-amber-800">{summary.partial}</p></div>
0177:           <div className="card"><p className="text-xs text-indigo-700">진행중</p><p className="text-lg font-semibold text-indigo-800">{summary.running}</p></div>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `177`
```text
0176:           <div className="card"><p className="text-xs text-amber-700">부분성공</p><p className="text-lg font-semibold text-amber-800">{summary.partial}</p></div>
0177:           <div className="card"><p className="text-xs text-indigo-700">진행중</p><p className="text-lg font-semibold text-indigo-800">{summary.running}</p></div>
0178:         </div>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `179`
```text
0178:         </div>
0179:       </SectionCard>
0180: 
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `181`
```text
0180: 
0181:       <SectionCard title="수집 이력 목록">
0182:         {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `229`
```text
0228:         ) : null}
0229:       </SectionCard>
0230: 
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `232`
```text
0231:       {selectedRun ? (
0232:         <SectionCard title="상세 메시지">
0233:           <div className="space-y-1 text-sm">
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `243`
```text
0242:           </div>
0243:         </SectionCard>
0244:       ) : null}
```

- ??: `src/pages/DashboardPage.tsx` / ??: `3`
```text
0002: import PageHeader from "@/components/common/PageHeader";
0003: import SectionCard from "@/components/common/SectionCard";
0004: import StatCard from "@/components/common/StatCard";
```

- ??: `src/pages/DashboardPage.tsx` / ??: `4`
```text
0003: import SectionCard from "@/components/common/SectionCard";
0004: import StatCard from "@/components/common/StatCard";
0005: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/DashboardPage.tsx` / ??: `53`
```text
0052: 
0053:       <SectionCard theme="dark">
0054:         <div className="hero-panel">
```

- ??: `src/pages/DashboardPage.tsx` / ??: `64`
```text
0063:         </div>
0064:       </SectionCard>
0065: 
```

- ??: `src/pages/DashboardPage.tsx` / ??: `68`
```text
0067:         {stats.map((stat) => (
0068:           <StatCard key={stat.title} title={stat.title} value={stat.value} icon={stat.icon} theme="dark" />
0069:         ))}
```

- ??: `src/pages/DashboardPage.tsx` / ??: `73`
```text
0072:       <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
0073:         <StatCard title="뉴스/공시 수집" value="준비중" icon={Newspaper} description="수집 파이프라인 연동 예정" badge="Roadmap" theme="dark" />
0074:         <StatCard title="리포트/GPT 자문" value="준비중" icon={FileText} description="리서치 자동화 연동 예정" badge="Roadmap" theme="dark" />
```

- ??: `src/pages/DashboardPage.tsx` / ??: `74`
```text
0073:         <StatCard title="뉴스/공시 수집" value="준비중" icon={Newspaper} description="수집 파이프라인 연동 예정" badge="Roadmap" theme="dark" />
0074:         <StatCard title="리포트/GPT 자문" value="준비중" icon={FileText} description="리서치 자동화 연동 예정" badge="Roadmap" theme="dark" />
0075:       </div>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `6`
```text
0005: import PageHeader from "@/components/common/PageHeader";
0006: import SectionCard from "@/components/common/SectionCard";
0007: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `160`
```text
0159: 
0160:       <SectionCard title="공시 수집 실행" theme="dark">
0161:         <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `208`
```text
0207:         ) : null}
0208:       </SectionCard>
0209: 
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `210`
```text
0209: 
0210:       <SectionCard title="검색" theme="dark">
0211:         <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `228`
```text
0227:         </form>
0228:       </SectionCard>
0229: 
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `230`
```text
0229: 
0230:       <SectionCard title="공시 목록" theme="dark">
0231:         {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `292`
```text
0291:         ) : null}
0292:       </SectionCard>
0293:     </div>
```

- ??: `src/pages/NewsPage.tsx` / ??: `6`
```text
0005: import PageHeader from "@/components/common/PageHeader";
0006: import SectionCard from "@/components/common/SectionCard";
0007: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/NewsPage.tsx` / ??: `131`
```text
0130: 
0131:       <SectionCard title="뉴스 수집 실행" theme="dark">
0132:         <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
```

- ??: `src/pages/NewsPage.tsx` / ??: `173`
```text
0172:         ) : null}
0173:       </SectionCard>
0174: 
```

- ??: `src/pages/NewsPage.tsx` / ??: `175`
```text
0174: 
0175:       <SectionCard title="검색" theme="dark">
0176:         <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
```

- ??: `src/pages/NewsPage.tsx` / ??: `193`
```text
0192:         </form>
0193:       </SectionCard>
0194: 
```

- ??: `src/pages/NewsPage.tsx` / ??: `195`
```text
0194: 
0195:       <SectionCard title="뉴스 목록" theme="dark">
0196:         {loading ? <p className="text-sm text-muted">로딩 중...</p> : null}
```

- ??: `src/pages/NewsPage.tsx` / ??: `256`
```text
0255:         ) : null}
0256:       </SectionCard>
0257:     </div>
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `6`
```text
0005: import PageHeader from "@/components/common/PageHeader";
0006: import SectionCard from "@/components/common/SectionCard";
0007: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `25`
```text
0024: 
0025:       <SectionCard title="조회 필터">
0026:         <div className="flex gap-2">
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `30`
```text
0029:         </div>
0030:       </SectionCard>
0031: 
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `32`
```text
0031: 
0032:       <SectionCard title="데이터 사전">
0033:         {items.length === 0 ? (
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `53`
```text
0052:         )}
0053:       </SectionCard>
0054:     </div>
```

- ??: `src/pages/StocksPage.tsx` / ??: `5`
```text
0004: import PageHeader from "@/components/common/PageHeader";
0005: import SectionCard from "@/components/common/SectionCard";
0006: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/StocksPage.tsx` / ??: `53`
```text
0052: 
0053:       <SectionCard title="검색">
0054:         <div className="flex flex-wrap gap-2">
```

- ??: `src/pages/StocksPage.tsx` / ??: `61`
```text
0060:         </div>
0061:       </SectionCard>
0062: 
```

- ??: `src/pages/StocksPage.tsx` / ??: `63`
```text
0062: 
0063:       <SectionCard title="종목 등록">
0064:         <form onSubmit={onCreate} className="grid grid-cols-1 gap-2 md:grid-cols-5">
```

- ??: `src/pages/StocksPage.tsx` / ??: `74`
```text
0073:         </form>
0074:       </SectionCard>
0075: 
```

- ??: `src/pages/StocksPage.tsx` / ??: `77`
```text
0076:       {editId ? (
0077:         <SectionCard title="종목 수정">
0078:           <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
```

- ??: `src/pages/StocksPage.tsx` / ??: `88`
```text
0087:           </div>
0088:         </SectionCard>
0089:       ) : null}
```

- ??: `src/pages/StocksPage.tsx` / ??: `91`
```text
0090: 
0091:       <SectionCard title="종목 목록">
0092:         {items.length === 0 ? (
```

- ??: `src/pages/StocksPage.tsx` / ??: `129`
```text
0128:         )}
0129:       </SectionCard>
0130:     </div>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `5`
```text
0004: import PageHeader from "@/components/common/PageHeader";
0005: import SectionCard from "@/components/common/SectionCard";
0006: import StatusBadge from "@/components/common/StatusBadge";
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `60`
```text
0059: 
0060:       <SectionCard title="필터">
0061:         <div className="flex flex-wrap gap-2">
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `69`
```text
0068:         </div>
0069:       </SectionCard>
0070: 
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `71`
```text
0070: 
0071:       <SectionCard title="관심종목 등록">
0072:         <form onSubmit={onCreate} className="grid grid-cols-1 gap-2 md:grid-cols-3">
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `84`
```text
0083:         </form>
0084:       </SectionCard>
0085: 
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `86`
```text
0085: 
0086:       <SectionCard title="관심종목 목록">
0087:         {items.length === 0 ? (
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `124`
```text
0123:         )}
0124:       </SectionCard>
0125:     </div>
```

### `card-dark`
- ?? ?? ?: `7`

- ??: `src/components/common/SectionCard.tsx` / ??: `13`
```text
0012:   return (
0013:     <section className={clsx("card", theme === "dark" && "card-dark", className)}>
0014:       {title ? <h3 className="section-title">{title}</h3> : null}
```

- ??: `src/components/common/StatCard.tsx` / ??: `15`
```text
0014:   return (
0015:     <article className={clsx("card", theme === "dark" && "card-dark")}>
0016:       <div className="flex items-start justify-between">
```

- ??: `src/index.css` / ??: `213`
```text
0212: 
0213: .card-dark {
0214:   color: var(--color-on-primary);
```

- ??: `src/index.css` / ??: `230`
```text
0229: 
0230: .card-dark .text-muted {
0231:   color: var(--color-muted-dark);
```

- ??: `src/index.css` / ??: `251`
```text
0250: 
0251: .card-dark .input-control,
0252: .card-dark .select-control,
```

- ??: `src/index.css` / ??: `252`
```text
0251: .card-dark .input-control,
0252: .card-dark .select-control,
0253: .card-dark .textarea-control {
```

- ??: `src/index.css` / ??: `253`
```text
0252: .card-dark .select-control,
0253: .card-dark .textarea-control {
0254:   border-color: var(--color-hairline-violet);
```

### `table-shell`
- ?? ?? ?: `8`

- ??: `src/index.css` / ??: `259`
```text
0258: 
0259: .table-shell {
0260:   overflow: auto;
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `196`
```text
0195:         {!loading && !error && items.length > 0 ? (
0196:           <div className="table-shell">
0197:             <table className="data-table min-w-[1550px]">
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `188`
```text
0187:         {!loading && !error && items.length > 0 ? (
0188:           <div className="table-shell">
0189:             <table className="data-table min-w-[1200px]">
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `236`
```text
0235:         {!loading && !error && items.length > 0 ? (
0236:           <div className="table-shell">
0237:             <table className="data-table min-w-[1440px]">
```

- ??: `src/pages/NewsPage.tsx` / ??: `201`
```text
0200:         {!loading && !error && items.length > 0 ? (
0201:           <div className="table-shell">
0202:             <table className="data-table min-w-[1380px]">
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `36`
```text
0035:         ) : (
0036:           <div className="table-shell">
0037:             <table className="data-table min-w-[900px]">
```

- ??: `src/pages/StocksPage.tsx` / ??: `95`
```text
0094:         ) : (
0095:           <div className="table-shell">
0096:             <table className="data-table min-w-[980px]">
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `90`
```text
0089:         ) : (
0090:           <div className="table-shell">
0091:             <table className="data-table min-w-[1200px]">
```

### `data-table`
- ?? ?? ?: `14`

- ??: `src/index.css` / ??: `266`
```text
0265: 
0266: .data-table {
0267:   width: 100%;
```

- ??: `src/index.css` / ??: `272`
```text
0271: 
0272: .data-table th,
0273: .data-table td {
```

- ??: `src/index.css` / ??: `273`
```text
0272: .data-table th,
0273: .data-table td {
0274:   min-height: 44px;
```

- ??: `src/index.css` / ??: `281`
```text
0280: 
0281: .data-table th {
0282:   color: var(--color-muted-light);
```

- ??: `src/index.css` / ??: `287`
```text
0286: 
0287: .data-table tbody tr:nth-child(odd) {
0288:   background: #fff;
```

- ??: `src/index.css` / ??: `291`
```text
0290: 
0291: .data-table tbody tr:nth-child(even) {
0292:   background: #fafafe;
```

- ??: `src/index.css` / ??: `295`
```text
0294: 
0295: .data-table tbody tr:hover {
0296:   background: #f1f5f9;
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `197`
```text
0196:           <div className="table-shell">
0197:             <table className="data-table min-w-[1550px]">
0198:               <thead>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `189`
```text
0188:           <div className="table-shell">
0189:             <table className="data-table min-w-[1200px]">
0190:               <thead>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `237`
```text
0236:           <div className="table-shell">
0237:             <table className="data-table min-w-[1440px]">
0238:               <thead>
```

- ??: `src/pages/NewsPage.tsx` / ??: `202`
```text
0201:           <div className="table-shell">
0202:             <table className="data-table min-w-[1380px]">
0203:               <thead>
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `37`
```text
0036:           <div className="table-shell">
0037:             <table className="data-table min-w-[900px]">
0038:               <thead>
```

- ??: `src/pages/StocksPage.tsx` / ??: `96`
```text
0095:           <div className="table-shell">
0096:             <table className="data-table min-w-[980px]">
0097:               <thead>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `91`
```text
0090:           <div className="table-shell">
0091:             <table className="data-table min-w-[1200px]">
0092:               <thead>
```

### `badge`
- ?? ?? ?: `70`

- ??: `src/components/common/StatCard.tsx` / ??: `9`
```text
0008:   icon: LucideIcon;
0009:   badge?: string;
0010:   theme?: "light" | "dark";
```

- ??: `src/components/common/StatCard.tsx` / ??: `13`
```text
0012: 
0013: function StatCard({ title, value, description, icon: Icon, badge, theme = "light" }: Props) {
0014:   return (
```

- ??: `src/components/common/StatCard.tsx` / ??: `20`
```text
0019:         </div>
0020:         {badge ? <span className="badge badge-slate">{badge}</span> : null}
0021:       </div>
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `13`
```text
0012: const toneMap: Record<Tone, string> = {
0013:   emerald: "badge-emerald",
0014:   amber: "badge-amber",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `14`
```text
0013:   emerald: "badge-emerald",
0014:   amber: "badge-amber",
0015:   rose: "badge-rose",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `15`
```text
0014:   amber: "badge-amber",
0015:   rose: "badge-rose",
0016:   blue: "badge-blue",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `16`
```text
0015:   rose: "badge-rose",
0016:   blue: "badge-blue",
0017:   slate: "badge-slate",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `17`
```text
0016:   blue: "badge-blue",
0017:   slate: "badge-slate",
0018: };
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `21`
```text
0020: const variantMap: Record<Variant, string> = {
0021:   positive: "badge-positive",
0022:   neutral: "badge-neutral",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `22`
```text
0021:   positive: "badge-positive",
0022:   neutral: "badge-neutral",
0023:   negative: "badge-negative",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `23`
```text
0022:   neutral: "badge-neutral",
0023:   negative: "badge-negative",
0024:   "risk-high": "badge-risk-high",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `24`
```text
0023:   negative: "badge-negative",
0024:   "risk-high": "badge-risk-high",
0025:   "risk-medium": "badge-risk-medium",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `25`
```text
0024:   "risk-high": "badge-risk-high",
0025:   "risk-medium": "badge-risk-medium",
0026:   "risk-low": "badge-risk-low",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `26`
```text
0025:   "risk-medium": "badge-risk-medium",
0026:   "risk-low": "badge-risk-low",
0027:   "risk-unknown": "badge-risk-unknown",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `27`
```text
0026:   "risk-low": "badge-risk-low",
0027:   "risk-unknown": "badge-risk-unknown",
0028:   "importance-high": "badge-importance-high",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `28`
```text
0027:   "risk-unknown": "badge-risk-unknown",
0028:   "importance-high": "badge-importance-high",
0029:   "importance-medium": "badge-importance-medium",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `29`
```text
0028:   "importance-high": "badge-importance-high",
0029:   "importance-medium": "badge-importance-medium",
0030:   "importance-low": "badge-importance-low",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `30`
```text
0029:   "importance-medium": "badge-importance-medium",
0030:   "importance-low": "badge-importance-low",
0031:   event: "badge-event",
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `31`
```text
0030:   "importance-low": "badge-importance-low",
0031:   event: "badge-event",
0032: };
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `34`
```text
0033: 
0034: function StatusBadge({ label, tone = "slate", variant }: Props) {
0035:   return <span className={clsx("badge", variant ? variantMap[variant] : toneMap[tone])}>{label}</span>;
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `35`
```text
0034: function StatusBadge({ label, tone = "slate", variant }: Props) {
0035:   return <span className={clsx("badge", variant ? variantMap[variant] : toneMap[tone])}>{label}</span>;
0036: }
```

- ??: `src/components/common/StatusBadge.tsx` / ??: `38`
```text
0037: 
0038: export default StatusBadge;
```

- ??: `src/index.css` / ??: `299`
```text
0298: 
0299: .badge {
0300:   display: inline-flex;
```

- ??: `src/index.css` / ??: `312`
```text
0311: 
0312: .badge-slate {
0313:   color: #475569;
```

- ??: `src/index.css` / ??: `318`
```text
0317: 
0318: .badge-blue {
0319:   color: #1e3a8a;
```

- ??: `src/index.css` / ??: `324`
```text
0323: 
0324: .badge-emerald,
0325: .badge-positive {
```

- ??: `src/index.css` / ??: `325`
```text
0324: .badge-emerald,
0325: .badge-positive {
0326:   color: #065f46;
```

- ??: `src/index.css` / ??: `331`
```text
0330: 
0331: .badge-amber,
0332: .badge-importance-medium,
```

- ??: `src/index.css` / ??: `332`
```text
0331: .badge-amber,
0332: .badge-importance-medium,
0333: .badge-risk-medium {
```

- ??: `src/index.css` / ??: `333`
```text
0332: .badge-importance-medium,
0333: .badge-risk-medium {
0334:   color: #92400e;
```

- ??: `src/index.css` / ??: `339`
```text
0338: 
0339: .badge-rose,
0340: .badge-negative,
```

- ??: `src/index.css` / ??: `340`
```text
0339: .badge-rose,
0340: .badge-negative,
0341: .badge-risk-high {
```

- ??: `src/index.css` / ??: `341`
```text
0340: .badge-negative,
0341: .badge-risk-high {
0342:   color: #9f1239;
```

- ??: `src/index.css` / ??: `347`
```text
0346: 
0347: .badge-neutral,
0348: .badge-importance-low,
```

- ??: `src/index.css` / ??: `348`
```text
0347: .badge-neutral,
0348: .badge-importance-low,
0349: .badge-risk-unknown {
```

- ??: `src/index.css` / ??: `349`
```text
0348: .badge-importance-low,
0349: .badge-risk-unknown {
0350:   color: #6b7280;
```

- ??: `src/index.css` / ??: `355`
```text
0354: 
0355: .badge-importance-high,
0356: .badge-risk-low,
```

- ??: `src/index.css` / ??: `356`
```text
0355: .badge-importance-high,
0356: .badge-risk-low,
0357: .badge-event {
```

- ??: `src/index.css` / ??: `357`
```text
0356: .badge-risk-low,
0357: .badge-event {
0358:   color: #1f1633;
```

- ??: `src/layouts/AdminLayout.tsx` / ??: `10`
```text
0009: import { appConfig } from "@/services/config/appConfig";
0010: import StatusBadge from "@/components/common/StatusBadge";
0011: 
```

- ??: `src/layouts/AdminLayout.tsx` / ??: `94`
```text
0093:           <div className="flex items-center gap-2">
0094:             <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone={dataSourceLabel === "api" ? "blue" : "slate"} />
0095:             <StatusBadge label={`API: ${apiStatus}`} tone={apiStatus === "정상" ? "emerald" : apiStatus === "오프라인" ? "rose" : "amber"} />
```

- ??: `src/layouts/AdminLayout.tsx` / ??: `95`
```text
0094:             <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone={dataSourceLabel === "api" ? "blue" : "slate"} />
0095:             <StatusBadge label={`API: ${apiStatus}`} tone={apiStatus === "정상" ? "emerald" : apiStatus === "오프라인" ? "rose" : "amber"} />
0096:           </div>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `5`
```text
0004: import SectionCard from "@/components/common/SectionCard";
0005: import StatusBadge from "@/components/common/StatusBadge";
0006: import { repositories } from "@/services";
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `227`
```text
0226:                     <td>{row.priority}</td>
0227:                     <td>{row.is_active ? <StatusBadge label="사용" tone="emerald" /> : <StatusBadge label="미사용" tone="slate" />}</td>
0228:                     <td>{row.description ?? "-"}</td>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `6`
```text
0005: import SectionCard from "@/components/common/SectionCard";
0006: import StatusBadge from "@/components/common/StatusBadge";
0007: import { repositories } from "@/services";
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `209`
```text
0208:                     <td>{r.target || "-"}</td>
0209:                     <td><StatusBadge label={statusLabel[r.status] || r.status} tone={statusTone[r.status] || "slate"} /></td>
0210:                     <td>{r.started_at}</td>
```

- ??: `src/pages/DashboardPage.tsx` / ??: `5`
```text
0004: import StatCard from "@/components/common/StatCard";
0005: import StatusBadge from "@/components/common/StatusBadge";
0006: import { useEffect, useMemo, useState } from "react";
```

- ??: `src/pages/DashboardPage.tsx` / ??: `59`
```text
0058:           <div className="mt-4 flex flex-wrap gap-2">
0059:             <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone="blue" />
0060:             <StatusBadge label={`종목 ${stockCount}건`} tone="emerald" />
```

- ??: `src/pages/DashboardPage.tsx` / ??: `60`
```text
0059:             <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone="blue" />
0060:             <StatusBadge label={`종목 ${stockCount}건`} tone="emerald" />
0061:             <StatusBadge label={`관심종목 ${watchlistCount}건`} tone="amber" />
```

- ??: `src/pages/DashboardPage.tsx` / ??: `61`
```text
0060:             <StatusBadge label={`종목 ${stockCount}건`} tone="emerald" />
0061:             <StatusBadge label={`관심종목 ${watchlistCount}건`} tone="amber" />
0062:           </div>
```

- ??: `src/pages/DashboardPage.tsx` / ??: `73`
```text
0072:       <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
0073:         <StatCard title="뉴스/공시 수집" value="준비중" icon={Newspaper} description="수집 파이프라인 연동 예정" badge="Roadmap" theme="dark" />
0074:         <StatCard title="리포트/GPT 자문" value="준비중" icon={FileText} description="리서치 자동화 연동 예정" badge="Roadmap" theme="dark" />
```

- ??: `src/pages/DashboardPage.tsx` / ??: `74`
```text
0073:         <StatCard title="뉴스/공시 수집" value="준비중" icon={Newspaper} description="수집 파이프라인 연동 예정" badge="Roadmap" theme="dark" />
0074:         <StatCard title="리포트/GPT 자문" value="준비중" icon={FileText} description="리서치 자동화 연동 예정" badge="Roadmap" theme="dark" />
0075:       </div>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `7`
```text
0006: import SectionCard from "@/components/common/SectionCard";
0007: import StatusBadge from "@/components/common/StatusBadge";
0008: import codes from "@/data/json/codes.json";
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `157`
```text
0156:         description="공시 이벤트 유형과 리스크 수준을 우선 확인하고, 투자 근거를 정리합니다."
0157:         action={<StatusBadge label={`미분류 리스크 ${unknownRiskCount}건`} tone={unknownRiskCount > 0 ? "amber" : "emerald"} />}
0158:       />
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `266`
```text
0265:                       <td>{d.disclosure_type ?? "-"}</td>
0266:                       <td><StatusBadge label={event} variant="event" /></td>
0267:                       <td><StatusBadge label={risk.label} variant={risk.variant} /></td>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `267`
```text
0266:                       <td><StatusBadge label={event} variant="event" /></td>
0267:                       <td><StatusBadge label={risk.label} variant={risk.variant} /></td>
0268:                       <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `268`
```text
0267:                       <td><StatusBadge label={risk.label} variant={risk.variant} /></td>
0268:                       <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
0269:                       <td>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `271`
```text
0270:                         <div className="flex flex-wrap gap-1">
0271:                           {tags.length > 0 ? tags.map((tag) => <StatusBadge key={`${d.id}-${tag}`} label={tag} tone="slate" />) : <StatusBadge label="미분류" tone="slate" />}
0272:                         </div>
```

- ??: `src/pages/NewsPage.tsx` / ??: `7`
```text
0006: import SectionCard from "@/components/common/SectionCard";
0007: import StatusBadge from "@/components/common/StatusBadge";
0008: import { repositories } from "@/services";
```

- ??: `src/pages/NewsPage.tsx` / ??: `128`
```text
0127:         description="수집된 뉴스를 투자 관점으로 점검하고 AI 요약·감성·중요도 신호를 확인합니다."
0128:         action={<StatusBadge label={`AI 처리 ${processedCount}/${items.length}`} tone="blue" />}
0129:       />
```

- ??: `src/pages/NewsPage.tsx` / ??: `231`
```text
0230:                       <td>{n.published_at ?? "-"}</td>
0231:                       <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
0232:                       <td><StatusBadge label={sentiment.label} variant={sentiment.variant} /></td>
```

- ??: `src/pages/NewsPage.tsx` / ??: `232`
```text
0231:                       <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
0232:                       <td><StatusBadge label={sentiment.label} variant={sentiment.variant} /></td>
0233:                       <td>
```

- ??: `src/pages/NewsPage.tsx` / ??: `235`
```text
0234:                         <div className="flex flex-wrap gap-1">
0235:                           {tags.length > 0 ? tags.map((tag) => <StatusBadge key={`${n.id}-${tag}`} label={tag} tone="slate" />) : <StatusBadge label="미분류" tone="slate" />}
0236:                         </div>
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `7`
```text
0006: import SectionCard from "@/components/common/SectionCard";
0007: import StatusBadge from "@/components/common/StatusBadge";
0008: 
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `44`
```text
0043:                   <tr key={`${i.table_name}-${i.column_name}-${idx}`}>
0044:                     <td><StatusBadge label={i.table_name} tone="blue" /></td>
0045:                     <td>{i.column_name || "테이블 설명"}</td>
```

- ??: `src/pages/StocksPage.tsx` / ??: `6`
```text
0005: import SectionCard from "@/components/common/SectionCard";
0006: import StatusBadge from "@/components/common/StatusBadge";
0007: import { repositories } from "@/services";
```

- ??: `src/pages/StocksPage.tsx` / ??: `51`
```text
0050:     <div className="space-y-4">
0051:       <PageHeader title="종목 관리" description="투자 검토 대상 종목의 기본 정보를 관리합니다." action={<StatusBadge label={`활성 ${activeCount} / 전체 ${items.length}`} tone="blue" />} />
0052: 
```

- ??: `src/pages/StocksPage.tsx` / ??: `116`
```text
0115:                     <td>{s.industry || "-"}</td>
0116:                     <td>{s.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
0117:                     <td>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `6`
```text
0005: import SectionCard from "@/components/common/SectionCard";
0006: import StatusBadge from "@/components/common/StatusBadge";
0007: import { repositories } from "@/services";
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `107`
```text
0106:                     <td><p className="font-semibold text-slate-900">{w.stock_code}</p><p className="text-xs text-slate-500">{w.stock_name}</p></td>
0107:                     <td><StatusBadge label={w.status} tone={statusToneMap[w.status] ?? "slate"} /></td>
0108:                     <td>{w.interest_reason || "-"}</td>
```

### `btn`
- ?? ?? ?: `41`

- ??: `src/index.css` / ??: `144`
```text
0143: 
0144: .btn {
0145:   display: inline-flex;
```

- ??: `src/index.css` / ??: `162`
```text
0161: 
0162: .btn:disabled {
0163:   opacity: 0.55;
```

- ??: `src/index.css` / ??: `167`
```text
0166: 
0167: .btn-primary {
0168:   color: var(--color-on-primary);
```

- ??: `src/index.css` / ??: `172`
```text
0171: 
0172: .app-shell-dark .btn-primary {
0173:   color: var(--color-ink-deep);
```

- ??: `src/index.css` / ??: `177`
```text
0176: 
0177: .btn-secondary {
0178:   color: var(--color-ink-deep);
```

- ??: `src/index.css` / ??: `183`
```text
0182: 
0183: .app-shell-dark .btn-secondary {
0184:   color: var(--color-on-primary);
```

- ??: `src/index.css` / ??: `189`
```text
0188: 
0189: .btn-danger {
0190:   color: #fff;
```

- ??: `src/index.css` / ??: `194`
```text
0193: 
0194: .btn-link {
0195:   color: var(--color-accent-violet);
```

- ??: `src/index.css` / ??: `200`
```text
0199: 
0200: .btn-on-light {
0201:   color: var(--color-ink-deep) !important;
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `152`
```text
0151:           <input className="input-control" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
0152:           <button type="submit" className="btn btn-primary">검색</button>
0153:           <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `153`
```text
0152:           <button type="submit" className="btn btn-primary">검색</button>
0153:           <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
0154:         </form>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `182`
```text
0181:           <div className="flex gap-2 md:col-span-4">
0182:             <button type="submit" className="btn btn-primary" disabled={submitLoading}>
0183:               {isEdit ? "저장" : "신규 등록"}
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `185`
```text
0184:             </button>
0185:             {isEdit ? <button type="button" className="btn btn-secondary" onClick={onCancelEdit}>취소</button> : null}
0186:           </div>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `229`
```text
0228:                     <td>{row.description ?? "-"}</td>
0229:                     <td><button type="button" className="btn btn-secondary" onClick={() => startEdit(row)}>수정</button></td>
0230:                     <td>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `232`
```text
0231:                       {row.is_active ? (
0232:                         <button type="button" className="btn btn-danger" onClick={() => onDeactivate(row.id)}>비활성화</button>
0233:                       ) : (
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `162`
```text
0161:           <div className="flex items-end gap-2">
0162:             <button type="submit" className="btn btn-primary">검색</button>
0163:             <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `163`
```text
0162:             <button type="submit" className="btn btn-primary">검색</button>
0163:             <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
0164:             <button type="button" className="btn btn-secondary inline-flex items-center gap-1" onClick={onRefresh}>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `164`
```text
0163:             <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
0164:             <button type="button" className="btn btn-secondary inline-flex items-center gap-1" onClick={onRefresh}>
0165:               <RotateCw size={14} /> 새로고침
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `216`
```text
0215:                       {r.message ? (
0216:                         <button type="button" className="btn btn-secondary" onClick={() => setSelectedRun(r)}>
0217:                           자세히
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `181`
```text
0180: 
0181:           <button className="btn btn-primary" onClick={onCollectForStock} disabled={collectLoading}>
0182:             {collectLoading ? "수집 중..." : "공시 수집 실행"}
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `184`
```text
0183:           </button>
0184:           <button className="btn btn-secondary" onClick={onCollectForWatchlist} disabled={collectLoading}>
0185:             관심종목 전체 수집
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `202`
```text
0201:             <div className="mt-3">
0202:               <button type="button" className="btn btn-secondary" onClick={() => navigate("/collection-runs")}>
0203:                 수집 이력 확인
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `224`
```text
0223:           <div className="flex gap-2">
0224:             <button type="submit" className="btn btn-primary">검색</button>
0225:             <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `225`
```text
0224:             <button type="submit" className="btn btn-primary">검색</button>
0225:             <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
0226:           </div>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `278`
```text
0277:                         {d.url ? (
0278:                           <a className="btn btn-secondary btn-on-light" href={d.url} target="_blank" rel="noreferrer">
0279:                             열기
```

- ??: `src/pages/NewsPage.tsx` / ??: `148`
```text
0147:           </select>
0148:           <button className="btn btn-primary" onClick={onCollect} disabled={collectLoading}>
0149:             {collectLoading ? "수집 중..." : "뉴스 수집 실행"}
```

- ??: `src/pages/NewsPage.tsx` / ??: `167`
```text
0166:             <div className="mt-3">
0167:               <button type="button" className="btn btn-secondary" onClick={() => navigate("/collection-runs")}>
0168:                 수집 이력 확인
```

- ??: `src/pages/NewsPage.tsx` / ??: `189`
```text
0188:           <div className="flex gap-2">
0189:             <button type="submit" className="btn btn-primary">검색</button>
0190:             <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
```

- ??: `src/pages/NewsPage.tsx` / ??: `190`
```text
0189:             <button type="submit" className="btn btn-primary">검색</button>
0190:             <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
0191:           </div>
```

- ??: `src/pages/NewsPage.tsx` / ??: `242`
```text
0241:                         {n.url ? (
0242:                           <a className="btn btn-secondary btn-on-light" href={n.url} target="_blank" rel="noreferrer">
0243:                             열기
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `28`
```text
0027:           <input className="input-control" placeholder="table_name 필터" value={tableName} onChange={(e) => setTableName(e.target.value)} />
0028:           <button className="btn btn-primary" onClick={load}>조회</button>
0029:         </div>
```

- ??: `src/pages/StocksPage.tsx` / ??: `59`
```text
0058:           </div>
0059:           <button className="btn btn-primary" onClick={load}>검색</button>
0060:         </div>
```

- ??: `src/pages/StocksPage.tsx` / ??: `71`
```text
0070:             <input className="input-control" placeholder="산업" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
0071:             <button className="btn btn-primary" type="submit">등록</button>
0072:           </div>
```

- ??: `src/pages/StocksPage.tsx` / ??: `84`
```text
0083:             <div className="flex gap-2">
0084:               <button className="btn btn-primary" onClick={onUpdate}>저장</button>
0085:               <button className="btn btn-secondary" onClick={() => setEditId(null)}>취소</button>
```

- ??: `src/pages/StocksPage.tsx` / ??: `85`
```text
0084:               <button className="btn btn-primary" onClick={onUpdate}>저장</button>
0085:               <button className="btn btn-secondary" onClick={() => setEditId(null)}>취소</button>
0086:             </div>
```

- ??: `src/pages/StocksPage.tsx` / ??: `119`
```text
0118:                       <div className="flex gap-2">
0119:                         <button className="btn btn-secondary inline-flex items-center gap-1" onClick={() => startEdit(s)}><PenLine size={13} />수정</button>
0120:                         <button className="btn btn-danger inline-flex items-center gap-1" onClick={() => onDeactivate(s.id)}><Trash2 size={13} />비활성화</button>
```

- ??: `src/pages/StocksPage.tsx` / ??: `120`
```text
0119:                         <button className="btn btn-secondary inline-flex items-center gap-1" onClick={() => startEdit(s)}><PenLine size={13} />수정</button>
0120:                         <button className="btn btn-danger inline-flex items-center gap-1" onClick={() => onDeactivate(s.id)}><Trash2 size={13} />비활성화</button>
0121:                       </div>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `67`
```text
0066:           <input className="input-control min-w-72 flex-1" placeholder="코드/종목명 검색" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
0067:           <button className="btn btn-primary" onClick={load}>검색</button>
0068:         </div>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `79`
```text
0078:           </select>
0079:           <button type="submit" className="btn btn-primary">등록</button>
0080:           <input className="input-control" placeholder="관심 사유" onChange={(e) => setForm({ ...form, interest_reason: e.target.value })} />
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `114`
```text
0113:                       <div className="flex gap-2">
0114:                         <button className="btn btn-secondary" onClick={() => onUpdate(w, { status: "관망" })}>상태수정</button>
0115:                         <button className="btn btn-danger" onClick={() => onDelete(w.id)}>삭제</button>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `115`
```text
0114:                         <button className="btn btn-secondary" onClick={() => onUpdate(w, { status: "관망" })}>상태수정</button>
0115:                         <button className="btn btn-danger" onClick={() => onDelete(w.id)}>삭제</button>
0116:                       </div>
```

### `input-control`
- ?? ?? ?: `31`

- ??: `src/index.css` / ??: `234`
```text
0233: 
0234: .input-control,
0235: .select-control,
```

- ??: `src/index.css` / ??: `251`
```text
0250: 
0251: .card-dark .input-control,
0252: .card-dark .select-control,
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `151`
```text
0150:           </select>
0151:           <input className="input-control" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
0152:           <button type="submit" className="btn btn-primary">검색</button>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `170`
```text
0169:           </select>
0170:           <input className="input-control" placeholder="rule_name" value={form.rule_name} onChange={(e) => setForm({ ...form, rule_name: e.target.value })} required />
0171:           <input className="input-control" placeholder="output_field" value={form.output_field} onChange={(e) => setForm({ ...form, output_field: e.target.value })} required />
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `171`
```text
0170:           <input className="input-control" placeholder="rule_name" value={form.rule_name} onChange={(e) => setForm({ ...form, rule_name: e.target.value })} required />
0171:           <input className="input-control" placeholder="output_field" value={form.output_field} onChange={(e) => setForm({ ...form, output_field: e.target.value })} required />
0172:           <textarea className="textarea-control md:col-span-2" placeholder="keywords (쉼표 구분)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} required />
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `173`
```text
0172:           <textarea className="textarea-control md:col-span-2" placeholder="keywords (쉼표 구분)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} required />
0173:           <input className="input-control" placeholder="output_value" value={form.output_value} onChange={(e) => setForm({ ...form, output_value: e.target.value })} required />
0174:           <textarea className="textarea-control" placeholder="description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `175`
```text
0174:           <textarea className="textarea-control" placeholder="description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
0175:           <input type="number" className="input-control" placeholder="score_delta" value={form.score_delta ?? 0} onChange={(e) => setForm({ ...form, score_delta: Number(e.target.value) })} />
0176:           <input type="number" className="input-control" placeholder="priority" value={form.priority ?? 100} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `176`
```text
0175:           <input type="number" className="input-control" placeholder="score_delta" value={form.score_delta ?? 0} onChange={(e) => setForm({ ...form, score_delta: Number(e.target.value) })} />
0176:           <input type="number" className="input-control" placeholder="priority" value={form.priority ?? 100} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
0177:           <label className="flex items-center gap-2 rounded-xl border border-[var(--color-hairline-cool)] px-3 py-2 text-sm">
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `130`
```text
0129:             <Search size={16} className="absolute left-3 top-8 text-slate-400" />
0130:             <input className="input-control pl-9" placeholder="collector_name" value={collectorName} onChange={(e) => setCollectorName(e.target.value)} />
0131:           </div>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `143`
```text
0142:             <p className="mb-1 text-xs text-slate-600">대상</p>
0143:             <input className="input-control" placeholder="target" value={target} onChange={(e) => setTarget(e.target.value)} />
0144:           </div>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `212`
```text
0211:         <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
0212:           <input className="input-control" placeholder="stock_id" value={stockId} onChange={(e) => setStockId(e.target.value)} />
0213:           <div className="relative md:col-span-2">
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `215`
```text
0214:             <Search size={16} className="absolute left-3 top-3.5 text-white/55" />
0215:             <input className="input-control pl-9" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
0216:           </div>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `217`
```text
0216:           </div>
0217:           <input className="input-control" placeholder="disclosure_type" value={disclosureType} onChange={(e) => setDisclosureType(e.target.value)} />
0218:           <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
```

- ??: `src/pages/NewsPage.tsx` / ??: `177`
```text
0176:         <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
0177:           <input className="input-control" placeholder="stock_id" value={stockId} onChange={(e) => setStockId(e.target.value)} />
0178:           <div className="relative md:col-span-2">
```

- ??: `src/pages/NewsPage.tsx` / ??: `180`
```text
0179:             <Search size={16} className="absolute left-3 top-3.5 text-white/55" />
0180:             <input className="input-control pl-9" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
0181:           </div>
```

- ??: `src/pages/NewsPage.tsx` / ??: `182`
```text
0181:           </div>
0182:           <input className="input-control" placeholder="source (ex. naver_news)" value={source} onChange={(e) => setSource(e.target.value)} />
0183:           <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
```

- ??: `src/pages/SchemaCommentsPage.tsx` / ??: `27`
```text
0026:         <div className="flex gap-2">
0027:           <input className="input-control" placeholder="table_name 필터" value={tableName} onChange={(e) => setTableName(e.target.value)} />
0028:           <button className="btn btn-primary" onClick={load}>조회</button>
```

- ??: `src/pages/StocksPage.tsx` / ??: `57`
```text
0056:             <Search size={16} className="absolute left-3 top-3.5 text-slate-400" />
0057:             <input className="input-control pl-9" placeholder="종목코드 또는 종목명" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
0058:           </div>
```

- ??: `src/pages/StocksPage.tsx` / ??: `65`
```text
0064:         <form onSubmit={onCreate} className="grid grid-cols-1 gap-2 md:grid-cols-5">
0065:           <input required className="input-control" placeholder="종목코드" value={form.stock_code} onChange={(e) => setForm({ ...form, stock_code: e.target.value })} />
0066:           <input required className="input-control" placeholder="종목명" value={form.stock_name} onChange={(e) => setForm({ ...form, stock_name: e.target.value })} />
```

- ??: `src/pages/StocksPage.tsx` / ??: `66`
```text
0065:           <input required className="input-control" placeholder="종목코드" value={form.stock_code} onChange={(e) => setForm({ ...form, stock_code: e.target.value })} />
0066:           <input required className="input-control" placeholder="종목명" value={form.stock_name} onChange={(e) => setForm({ ...form, stock_name: e.target.value })} />
0067:           <input className="input-control" placeholder="시장" value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} />
```

- ??: `src/pages/StocksPage.tsx` / ??: `67`
```text
0066:           <input required className="input-control" placeholder="종목명" value={form.stock_name} onChange={(e) => setForm({ ...form, stock_name: e.target.value })} />
0067:           <input className="input-control" placeholder="시장" value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} />
0068:           <input className="input-control" placeholder="섹터" value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })} />
```

- ??: `src/pages/StocksPage.tsx` / ??: `68`
```text
0067:           <input className="input-control" placeholder="시장" value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} />
0068:           <input className="input-control" placeholder="섹터" value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })} />
0069:           <div className="flex gap-2">
```

- ??: `src/pages/StocksPage.tsx` / ??: `70`
```text
0069:           <div className="flex gap-2">
0070:             <input className="input-control" placeholder="산업" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
0071:             <button className="btn btn-primary" type="submit">등록</button>
```

- ??: `src/pages/StocksPage.tsx` / ??: `79`
```text
0078:           <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
0079:             <input className="input-control" placeholder="종목명" value={editForm.stock_name || ""} onChange={(e) => setEditForm({ ...editForm, stock_name: e.target.value })} />
0080:             <input className="input-control" placeholder="시장" value={editForm.market || ""} onChange={(e) => setEditForm({ ...editForm, market: e.target.value })} />
```

- ??: `src/pages/StocksPage.tsx` / ??: `80`
```text
0079:             <input className="input-control" placeholder="종목명" value={editForm.stock_name || ""} onChange={(e) => setEditForm({ ...editForm, stock_name: e.target.value })} />
0080:             <input className="input-control" placeholder="시장" value={editForm.market || ""} onChange={(e) => setEditForm({ ...editForm, market: e.target.value })} />
0081:             <input className="input-control" placeholder="섹터" value={editForm.sector || ""} onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })} />
```

- ??: `src/pages/StocksPage.tsx` / ??: `81`
```text
0080:             <input className="input-control" placeholder="시장" value={editForm.market || ""} onChange={(e) => setEditForm({ ...editForm, market: e.target.value })} />
0081:             <input className="input-control" placeholder="섹터" value={editForm.sector || ""} onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })} />
0082:             <input className="input-control" placeholder="산업" value={editForm.industry || ""} onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })} />
```

- ??: `src/pages/StocksPage.tsx` / ??: `82`
```text
0081:             <input className="input-control" placeholder="섹터" value={editForm.sector || ""} onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })} />
0082:             <input className="input-control" placeholder="산업" value={editForm.industry || ""} onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })} />
0083:             <div className="flex gap-2">
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `66`
```text
0065:           </select>
0066:           <input className="input-control min-w-72 flex-1" placeholder="코드/종목명 검색" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
0067:           <button className="btn btn-primary" onClick={load}>검색</button>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `80`
```text
0079:           <button type="submit" className="btn btn-primary">등록</button>
0080:           <input className="input-control" placeholder="관심 사유" onChange={(e) => setForm({ ...form, interest_reason: e.target.value })} />
0081:           <input className="input-control" placeholder="진입 조건" onChange={(e) => setForm({ ...form, entry_condition: e.target.value })} />
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `81`
```text
0080:           <input className="input-control" placeholder="관심 사유" onChange={(e) => setForm({ ...form, interest_reason: e.target.value })} />
0081:           <input className="input-control" placeholder="진입 조건" onChange={(e) => setForm({ ...form, entry_condition: e.target.value })} />
0082:           <input className="input-control" placeholder="제외 조건" onChange={(e) => setForm({ ...form, exit_condition: e.target.value })} />
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `82`
```text
0081:           <input className="input-control" placeholder="진입 조건" onChange={(e) => setForm({ ...form, entry_condition: e.target.value })} />
0082:           <input className="input-control" placeholder="제외 조건" onChange={(e) => setForm({ ...form, exit_condition: e.target.value })} />
0083:         </form>
```

### `select-control`
- ?? ?? ?: `21`

- ??: `src/index.css` / ??: `235`
```text
0234: .input-control,
0235: .select-control,
0236: .textarea-control {
```

- ??: `src/index.css` / ??: `252`
```text
0251: .card-dark .input-control,
0252: .card-dark .select-control,
0253: .card-dark .textarea-control {
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `133`
```text
0132:         <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
0133:           <select className="select-control" value={targetType} onChange={(e) => setTargetType(e.target.value)}>
0134:             <option value="">전체 대상</option>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `138`
```text
0137:           </select>
0138:           <select className="select-control" value={ruleGroup} onChange={(e) => setRuleGroup(e.target.value)}>
0139:             <option value="">전체 그룹</option>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `146`
```text
0145:           </select>
0146:           <select className="select-control" value={isActive} onChange={(e) => setIsActive(e.target.value)}>
0147:             <option value="">전체 상태</option>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `159`
```text
0158:         <form onSubmit={onSubmit} className="grid grid-cols-1 gap-2 md:grid-cols-4">
0159:           <select className="select-control" value={form.target_type} onChange={(e) => setForm({ ...form, target_type: e.target.value })}>
0160:             <option value="news">news</option>
```

- ??: `src/pages/ClassificationRulesPage.tsx` / ??: `163`
```text
0162:           </select>
0163:           <select className="select-control" value={form.rule_group} onChange={(e) => setForm({ ...form, rule_group: e.target.value })}>
0164:             <option value="tag">tag</option>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `134`
```text
0133:             <p className="mb-1 text-xs text-slate-600">상태</p>
0134:             <select className="select-control" value={status} onChange={(e) => setStatus(e.target.value)}>
0135:               <option value="">전체</option>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `147`
```text
0146:             <p className="mb-1 text-xs text-slate-600">조회 건수</p>
0147:             <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
0148:               <option value="20">20</option>
```

- ??: `src/pages/CollectionRunsPage.tsx` / ??: `155`
```text
0154:             <p className="mb-1 text-xs text-slate-600">시작 위치</p>
0155:             <select className="select-control" value={offset} onChange={(e) => setOffset(e.target.value)}>
0156:               <option value="0">0</option>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `162`
```text
0161:         <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
0162:           <select className="select-control md:col-span-2" value={collectStockId} onChange={(e) => setCollectStockId(e.target.value)}>
0163:             <option value="">종목 선택</option>
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `169`
```text
0168: 
0169:           <select className="select-control" value={collectDays} onChange={(e) => setCollectDays(e.target.value)}>
0170:             {(codes as any).disclosureCollectDays?.map((d: { value: number; label: string }) => (
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `175`
```text
0174: 
0175:           <select className="select-control" value={collectPageCount} onChange={(e) => setCollectPageCount(e.target.value)}>
0176:             {(codes as any).disclosurePageCount?.map((d: { value: number; label: string }) => (
```

- ??: `src/pages/DisclosuresPage.tsx` / ??: `218`
```text
0217:           <input className="input-control" placeholder="disclosure_type" value={disclosureType} onChange={(e) => setDisclosureType(e.target.value)} />
0218:           <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
0219:             <option value="20">20</option>
```

- ??: `src/pages/NewsPage.tsx` / ??: `133`
```text
0132:         <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
0133:           <select className="select-control md:col-span-2" value={collectStockId} onChange={(e) => setCollectStockId(e.target.value)}>
0134:             <option value="">종목 선택</option>
```

- ??: `src/pages/NewsPage.tsx` / ??: `139`
```text
0138:           </select>
0139:           <select className="select-control" value={collectDisplay} onChange={(e) => setCollectDisplay(e.target.value)}>
0140:             <option value="10">10건</option>
```

- ??: `src/pages/NewsPage.tsx` / ??: `144`
```text
0143:           </select>
0144:           <select className="select-control" value={collectSort} onChange={(e) => setCollectSort(e.target.value)}>
0145:             <option value="date">최신순(date)</option>
```

- ??: `src/pages/NewsPage.tsx` / ??: `183`
```text
0182:           <input className="input-control" placeholder="source (ex. naver_news)" value={source} onChange={(e) => setSource(e.target.value)} />
0183:           <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
0184:             <option value="20">20</option>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `62`
```text
0061:         <div className="flex flex-wrap gap-2">
0062:           <select className="select-control" value={status} onChange={(e) => setStatus(e.target.value)}>
0063:             <option value="">전체 상태</option>
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `73`
```text
0072:         <form onSubmit={onCreate} className="grid grid-cols-1 gap-2 md:grid-cols-3">
0073:           <select className="select-control" value={form.stock_id} onChange={(e) => setForm({ ...form, stock_id: Number(e.target.value) })}>
0074:             {stocks.map((s) => <option key={s.id} value={s.id}>{s.stock_code} - {s.stock_name}</option>)}
```

- ??: `src/pages/WatchlistPage.tsx` / ??: `76`
```text
0075:           </select>
0076:           <select className="select-control" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
0077:             {codes.watchlistStatus.map((s) => <option key={s} value={s}>{s}</option>)}
```

## 9. npm run build ?? ??

- ??: ??

### ?? ?? ?? ??

```text
��
 
 >   d r c t - a s s e t - o f f i c e - f r o n t e n d @ 0 . 1 . 0   b u i l d 
 
 >   t s c   - b   & &   v i t e   b u i l d 
 
 
 
  [ 3 6 m v i t e   v 5 . 4 . 2 1    [ 3 2 m b u i l d i n g   f o r   p r o d u c t i o n . . .  [ 3 6 m  [ 3 9 m 
 
 t r a n s f o r m i n g . . . 
 
  [ 3 2 m ' [ 3 9 m   1 6 9 3   m o d u l e s   t r a n s f o r m e d . 
 
 r e n d e r i n g   c h u n k s . . . 
 
 c o m p u t i n g   g z i p   s i z e . . . 
 
  [ 2 m d i s t /  [ 2 2 m  [ 3 2 m i n d e x . h t m l                                    [ 3 9 m  [ 1 m  [ 2 m     0 . 4 2   k B  [ 2 2 m  [ 1 m  [ 2 2 m  [ 2 m   %  g z i p :     0 . 2 9   k B  [ 2 2 m 
 
  [ 2 m d i s t /  [ 2 2 m  [ 3 5 m a s s e t s / i n d e x - D F s p W d m z . c s s      [ 3 9 m  [ 1 m  [ 2 m   2 0 . 1 4   k B  [ 2 2 m  [ 1 m  [ 2 2 m  [ 2 m   %  g z i p :     4 . 9 0   k B  [ 2 2 m 
 
  [ 2 m d i s t /  [ 2 2 m  [ 3 6 m a s s e t s / i n d e x - B t u N x t K E . j s        [ 3 9 m  [ 1 m  [ 2 m 2 3 3 . 1 3   k B  [ 2 2 m  [ 1 m  [ 2 2 m  [ 2 m   %  g z i p :   7 0 . 2 9   k B  [ 2 2 m 
 
  [ 3 2 m '  b u i l t   i n   2 . 2 4 s  [ 3 9 m 
 
 
```
