# Adding the reporting script for the iPhone check

Only a project whose builder lanes run the iPhone check needs this. The plugin ships no reporting script, so each project writes its own. Until it does, those lanes' checks report `iPhone check did not run — whole check: the app lacks its reporting script`. Nothing else in the lane changes.

## How the pilot gets a reading

`open` adds the `superheroes-reading` query parameter to the page URL. The name lives in one place, `READING_PARAM` in `lib/iphone_check.py`. The value is a loopback address, `http://127.0.0.1:<port>/<token>`.

The pilot then runs `read --run-dir <dir> --token <token> --where browser|installed`, with the run dir and token that `open` gave it. `read` listens on that address only for the length of the call. The accepted reading comes back on its JSON output as `reading`, next to `labels`. The full procedure is in `skills/test-pilot-execute/reference/execution-steps.md`, section The iPhone check.

## What the script does

- It reads the address from the `superheroes-reading` parameter of the page URL. When the parameter is absent, it does nothing.
- It sends each reading as a JSON body with `fetch`, using `method: "POST"`, `mode: "no-cors"`, and `Content-Type: text/plain`. That header keeps the browser from sending a preflight request. The target is that exact address.
- It needs no bridge or helper from outside the page.
- It sends on page load, on focus in and out, on input, on visual-viewport resize, on visibility change, and every 500 ms. `read` accepts only a reading taken after its call began, so a script that posts once on load is never read.
- It keeps each body under 1 MiB.

## The reading

The shape of a reading is defined by `buildReading()` in `lib/tests/fixtures/iphone/reading-page.html`, the reference implementation, and accepted by `accept_reading` in `lib/iphone_check.py`. The two examples show what that implementation sends. They are illustrations, not a second protocol.

A text field focused after typing `hello`:

```json
{
  "visibleHeight": 412,
  "focused": {"tag": "input", "type": "text", "id": "name", "name": "name"},
  "value": "hello",
  "valueWithheld": false,
  "where": "browser",
  "visibility": "visible",
  "page": "http://localhost:3000/login",
  "takenAt": 1767225600000
}
```

A password field focused. The reading has no `value` key:

```json
{
  "visibleHeight": 412,
  "focused": {"tag": "input", "type": "password", "id": "secret", "name": "secret"},
  "valueWithheld": true,
  "where": "browser",
  "visibility": "visible",
  "page": "http://localhost:3000/login",
  "takenAt": 1767225600000
}
```

The check is about four values:

- `visibleHeight` is the height of the visual viewport. It shrinks when the keyboard rises.
- `focused` is the focused element, or `null` when nothing is focused. Give each field an `id`, or at least a `name`. The pilot names a field by its `id`, else `name:<name>`.
- `value` is that element's value.
- `where` is `installed` when `navigator.standalone` is true or `(display-mode: standalone)` matches. Otherwise it is `browser`.

`read` decides whether to accept each reading. The rules live in `accept_reading` in `lib/iphone_check.py`, the one home for them. Send what the reference implementation sends, to the address exactly as the page URL gave it, and keep sending fresh readings, so that function takes them. If `read` refuses your readings, read that function.

## Two rules

The script must be absent from the app the project's real users get, or do nothing there. Include it only in the development build, through a development-only bundle entry or a build-time flag. A check for the query parameter is not enough, because anyone can add a query parameter to a URL.

A reading never carries any part of a password field's value. When the focused field is a password field, send `valueWithheld: true` and no `value`. `read` also strips one, but the value must never leave the page.

## Limits

- The page source served at the page URL must contain the text `superheroes-reading`, for example with the script inline in the page. The pilot searches that source to tell a missing script from a reading that never came. A script loaded only from a separate bundle file reads as "the app lacks its reporting script".
- In the installed web app, the address survives only when the app opens a URL that keeps the query. A manifest `start_url` that drops it gives `no page reading from the installed app`. Keep the query in the development build's start URL.
- The address is plain `http` on the loopback. A development Content-Security-Policy must let `connect-src` reach `http://127.0.0.1:*`. A page served over `https` that sends to it has not been exercised. If such a page sends no readings, check that first.
- An HTTP reading cannot name the phone it came from. Its `phone` label is the phone the page was opened on.

## A working example

`lib/tests/fixtures/iphone/reading-page.html` is a complete reporting script. Replace its `__READING_PARAM__` placeholder with `superheroes-reading` before use. A copy used unchanged sends nothing. The example has no development-only gate, so add one.
