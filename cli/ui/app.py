from __future__ import annotations

from cli.constants import ACTION_SPECS
from cli.services import run_seed_action
from cli.ui.config import BINDINGS, MAX_PARAM_FIELDS, MENU
from cli.ui.styles import APP_CSS
from cli.ui.widgets import OutputLog
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static, TextArea


class SeederCLIApp(App):
    CSS = APP_CSS
    BINDINGS = BINDINGS

    def __init__(self) -> None:
        super().__init__()
        self.menu_stack = ["main"]
        self.cursor = 0
        self.selected_action: str | None = None
        self.param_keys: list[str] = []
        self._is_job_running = False

    @property
    def current_menu(self) -> str:
        return self.menu_stack[-1]

    def compose(self) -> ComposeResult:
        yield Static(
            "Seeder CLI\n"
            "Arrows/Enter: menu | Tab/Shift+Tab: params | Ctrl+R: run",
            id="title",
        )
        yield Static("Status: idle", id="status")
        with Horizontal(id="workspace"):
            with Vertical(id="left_pane"):
                yield Static("Main", id="left_title")
                yield Static("", id="menu")
                yield Static("", id="params_header")
                for idx in range(1, MAX_PARAM_FIELDS + 1):
                    yield Static("", id=f"label_{idx}", classes="param_label")
                    yield Input(id=f"param_{idx}", classes="param_input", value="")
                yield TextArea("", id="prompt_area", classes="prompt_area")
                yield Static("", id="hint")
            with Vertical(id="right_pane"):
                yield Static("Logs", id="logs_title")
                yield OutputLog(id="logs", markup=False, highlight=False)

    def on_mount(self) -> None:
        self.action_focus_menu()
        self._render_menu()
        self._set_params_visible(False)
        self._update_left_title()
        self._update_menu_hint()
        self._log("Ready.")

    def _log(self, message: str) -> None:
        log = self.query_one("#logs", OutputLog)
        log.write(message)
        try:
            log.scroll_end(animate=False)
        except Exception:
            pass

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(f"Status: {message}")

    def action_clear_logs(self) -> None:
        self.query_one("#logs", OutputLog).clear()

    def action_focus_logs(self) -> None:
        self.set_focus(self.query_one("#logs", OutputLog))

    def action_logs_page_up(self) -> None:
        log = self.query_one("#logs", OutputLog)
        try:
            log.scroll_page_up(animate=False)
        except Exception:
            try:
                log.scroll_to(y=max(log.scroll_y - 10, 0), animate=False)
            except Exception:
                pass

    def action_logs_page_down(self) -> None:
        log = self.query_one("#logs", OutputLog)
        try:
            log.scroll_page_down(animate=False)
        except Exception:
            try:
                log.scroll_to(y=log.scroll_y + 10, animate=False)
            except Exception:
                pass

    def _menu_items(self) -> list[tuple[str, str]]:
        return MENU[self.current_menu]

    def _update_left_title(self) -> None:
        crumbs = list(self.menu_stack)
        if self._in_params_mode() and self.selected_action:
            crumbs.append(self.selected_action)
            crumbs.append("params")
        else:
            items = self._menu_items()
            if items:
                current_key = items[self.cursor][1]
                crumbs.append(f"@{current_key}")

        self.query_one("#left_title", Static).update(" > ".join(crumbs))

    def _update_menu_hint(self) -> None:
        self.query_one("#hint", Static).update(
            "Enter to open | Esc to go back | logs show timings"
        )

    def _visible_param_fields(self) -> list[Input]:
        fields: list[Input] = []
        for idx in range(1, MAX_PARAM_FIELDS + 1):
            field = self.query_one(f"#param_{idx}", Input)
            if field.display:
                fields.append(field)
        return fields

    def _set_cursor_to_end(self, field: Input) -> None:
        try:
            field.cursor_position = len(field.value)
        except Exception:
            pass

    def _update_params_preview(self) -> None:
        if not self.param_keys:
            self.query_one("#hint", Static).update("No parameters required")
            return

        pairs: list[str] = []
        for idx, key in enumerate(self.param_keys, start=1):
            field = self.query_one(f"#param_{idx}", Input)
            val = field.value.strip()
            if val == "":
                val = "<empty>"
            pairs.append(f"{key}={val}")

        self.query_one("#hint", Static).update(
            "Tab/Shift+Tab: switch fields | " + ", ".join(pairs)
        )

    def _render_menu(self) -> None:
        lines: list[str] = []
        for idx, (title, _key) in enumerate(self._menu_items()):
            prefix = ">" if idx == self.cursor else " "
            lines.append(f"{prefix} {title}")
        self.query_one("#menu", Static).update("\n".join(lines))
        self._update_left_title()

    def _set_params_visible(self, visible: bool) -> None:
        header = self.query_one("#params_header", Static)
        menu = self.query_one("#menu", Static)
        prompt_area = self.query_one("#prompt_area", TextArea)
        header.display = visible
        menu.display = not visible
        prompt_area.display = False

        for idx in range(1, MAX_PARAM_FIELDS + 1):
            label = self.query_one(f"#label_{idx}", Static)
            field = self.query_one(f"#param_{idx}", Input)
            label.display = visible
            field.display = visible

    def _in_params_mode(self) -> bool:
        return self.query_one("#params_header", Static).display

    def _select_action(self, action: str) -> None:
        self.selected_action = action
        self.query_one("#params_header", Static).update(f"Action: {action}")

        defaults = ACTION_SPECS.get(action, {}).get("defaults", {})
        self.param_keys = list(defaults.keys())

        self._set_params_visible(True)
        prompt_area = self.query_one("#prompt_area", TextArea)
        use_prompt_area = action == "llm_query"
        prompt_area.display = use_prompt_area
        prompt_area.text = ""

        for idx in range(1, MAX_PARAM_FIELDS + 1):
            label = self.query_one(f"#label_{idx}", Static)
            field = self.query_one(f"#param_{idx}", Input)
            field.placeholder = ""

            if idx <= len(self.param_keys):
                key = self.param_keys[idx - 1]
                label.update(key)
                if use_prompt_area and key == "prompt":
                    field.display = False
                    prompt_area.text = str(defaults[key])
                else:
                    field.value = str(defaults[key])
                    field.placeholder = str(defaults[key])
            else:
                label.display = False
                field.display = False
                field.value = ""

        if self.param_keys:
            self._update_params_preview()
        else:
            self.query_one("#hint", Static).update("No parameters required")
        self._update_left_title()

    def _current_menu_key(self) -> str:
        return self._menu_items()[self.cursor][1]

    def action_menu_up(self) -> None:
        if self._in_params_mode():
            self.action_focus_prev_param()
            return
        self.cursor = (self.cursor - 1) % len(self._menu_items())
        self._render_menu()

    def action_menu_down(self) -> None:
        if self._in_params_mode():
            self.action_focus_next_param()
            return
        self.cursor = (self.cursor + 1) % len(self._menu_items())
        self._render_menu()

    def action_menu_select(self) -> None:
        if self._in_params_mode():
            if not self._visible_param_fields():
                self.action_run_action()
                return
            self.action_focus_next_param()
            return

        key = self._current_menu_key()
        if key == "main" and self.current_menu != "main":
            self.action_go_back()
            return

        if key in MENU:
            self.menu_stack.append(key)
            self.cursor = 0
            self._render_menu()
            self.action_focus_menu()
            self._update_menu_hint()
            return

        self._select_action(key)
        self._log(f"Selected: {key}")
        if self.param_keys:
            if key == "llm_query":
                self.set_focus(self.query_one("#prompt_area", TextArea))
            else:
                self.action_focus_params()

    def action_focus_menu(self) -> None:
        self.set_focus(None)

    def action_focus_params(self) -> None:
        fields = self._visible_param_fields()
        if not fields:
            self.action_focus_menu()
            return
        first = fields[0]
        self.set_focus(first)
        self._set_cursor_to_end(first)

    def action_focus_next_param(self) -> None:
        fields = self._visible_param_fields()
        if not fields:
            self.action_focus_menu()
            return

        focused = self.focused
        if focused not in fields:
            target = fields[0]
        else:
            idx = (fields.index(focused) + 1) % len(fields)
            target = fields[idx]

        self.set_focus(target)
        self._set_cursor_to_end(target)

    def action_focus_prev_param(self) -> None:
        fields = self._visible_param_fields()
        if not fields:
            self.action_focus_menu()
            return

        focused = self.focused
        if focused not in fields:
            target = fields[-1]
        else:
            idx = (fields.index(focused) - 1) % len(fields)
            target = fields[idx]

        self.set_focus(target)
        self._set_cursor_to_end(target)

    def action_go_back(self) -> None:
        if self._in_params_mode():
            self._set_params_visible(False)
            self.param_keys = []
            self.selected_action = None
            self._update_menu_hint()
            self._update_left_title()
            self.action_focus_menu()
            return

        if self.focused == self.query_one("#logs", OutputLog):
            self.action_focus_menu()
            return

        if len(self.menu_stack) <= 1:
            self.action_focus_menu()
            return

        self.menu_stack.pop()
        self.cursor = 0
        self._render_menu()
        self._update_menu_hint()
        self.action_focus_menu()

    def _log_outcome_metrics(self, outcome) -> None:
        self._log(
            f"timings_ms: total={outcome.duration_ms}, connect={outcome.connect_ms}, execute={outcome.execute_ms}"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.input.id or not event.input.id.startswith("param_"):
            return

        fields = self._visible_param_fields()
        if event.input not in fields:
            return

        idx = fields.index(event.input)
        if idx == len(fields) - 1:
            self.action_run_action()
        else:
            self.action_focus_next_param()

    def on_input_changed(self, event: Input.Changed) -> None:
        if not event.input.id or not event.input.id.startswith("param_"):
            return
        self._update_params_preview()

    def on_key(self, event: events.Key) -> None:
        if event.key == "tab":
            if self._in_params_mode():
                self.action_focus_next_param()
            event.prevent_default()
            event.stop()
            return

        if event.key == "shift+tab":
            if self._in_params_mode():
                self.action_focus_prev_param()
            event.prevent_default()
            event.stop()
            return

    def _parse_params(self) -> dict:
        defaults = ACTION_SPECS.get(self.selected_action, {}).get("defaults", {})
        params: dict = {}
        prompt_area = self.query_one("#prompt_area", TextArea)

        for idx, key in enumerate(self.param_keys, start=1):
            if self.selected_action == "llm_query" and key == "prompt" and prompt_area.display:
                raw = prompt_area.text.strip()
            else:
                field = self.query_one(f"#param_{idx}", Input)
                raw = field.value.strip()
            default = defaults[key]
            if raw == "":
                params[key] = default
                continue

            if isinstance(default, bool):
                params[key] = raw.lower() in {"1", "true", "yes", "y"}
            elif isinstance(default, int):
                params[key] = int(raw)
            elif isinstance(default, float):
                params[key] = float(raw)
            else:
                params[key] = raw

        for key, value in params.items():
            if not key.startswith("min_"):
                continue
            max_key = key.replace("min_", "max_", 1)
            if max_key in params and isinstance(value, (int, float)):
                if value > params[max_key]:
                    raise ValueError(f"{key} cannot be greater than {max_key}")

        return params

    def _reset_param_fields(self) -> None:
        prompt_area = self.query_one("#prompt_area", TextArea)
        prompt_area.text = ""
        for idx in range(1, MAX_PARAM_FIELDS + 1):
            field = self.query_one(f"#param_{idx}", Input)
            if field.display:
                field.value = ""

    def action_run_action(self) -> None:
        if self._is_job_running:
            self._log("Already running. Wait for current action to finish.")
            return

        action = self.selected_action
        if action not in ACTION_SPECS:
            self._log(f"Unknown action: {action}")
            return

        try:
            params = self._parse_params()
        except Exception as exc:
            self._log(f"Invalid parameter: {exc}")
            return

        self._log(f"Running: {action}")
        self._set_status(f"running {action}")
        self._is_job_running = True
        self.run_worker(self._run(action, params), exclusive=True)

    async def _run(self, action: str, params: dict) -> None:
        had_error = False
        try:
            outcome = await run_seed_action(action, params)

            # Add separator before results
            self._log("\n" + "=" * 60)
            self._log(f"Action: {action}")
            self._log("=" * 60)

            if action in ("table_counts", "level1", "level2", "level3", "all", "llm_query") and outcome.logs:
                for line in outcome.logs:
                    self._log(line)
                self._log("-" * 60)

            self._log_outcome_metrics(outcome)

            if outcome.error:
                self._log(f"Error: {outcome.error}")
                self._set_status("error")
                had_error = True
                return

            if outcome.inserted is None:
                self._log(f"Done: {action}")
            else:
                self._log(f"Done: {action}, inserted={outcome.inserted}")
            self._set_status("completed")
        finally:
            self._reset_param_fields()
            self._is_job_running = False
            if not had_error:
                self._set_status("idle")
