from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"D:\POJ\NodeMaster")
OUTPUT = ROOT / "ui-analysis-output"
EVIDENCE = OUTPUT / "evidence"
BUNDLE = OUTPUT / "ui-analysis-bundle-v1"
TEMPLATE = (
    ROOT
    / ".agents"
    / "skills"
    / "generate-ui-analysis-index"
    / "assets"
    / "bundle-template"
    / "blank"
)
SOURCE_UI = EVIDENCE / "source-ui.json"

ID_RE = re.compile(r"[^a-z0-9_.:-]+")
SKIP_PARTS = {
    "bin", "obj", "packages", "node_modules", ".git", ".vs", "testresults",
    "coverage", "thirdparty", "third-party",
}
EXCLUDED_TOPS = {"task", "tmp", ".tmp", "outputs"}
EVENT_NAMES = (
    "Click",
    "Checked",
    "Unchecked",
    "SelectionChanged",
    "TextChanged",
    "ValueChanged",
    "Loaded",
    "MouseDown",
    "MouseUp",
    "TouchDown",
    "PreviewMouseDown",
    "ButtonBase.Click",
)
DIAGNOSTIC_CATEGORIES = {
    "unconfirmed_screen",
    "unconfirmed_element",
    "dynamic_element",
    "uncertain_transition",
    "unparsed_text",
    "requires_runtime_calibration",
}


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp932", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("/", "\\")


def is_skipped(path: Path) -> bool:
    parts = {part.lower() for part in path.relative_to(ROOT).parts}
    return bool(parts & SKIP_PARTS) or any(
        part.lower().startswith("ui-analysis-output") for part in parts
    )


def dedupe(values: list[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        value = html.unescape(str(value)).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def literal(value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value).strip()
    if (
        not value
        or value.startswith("{")
        or value.startswith("@")
        or value.lower() in {"true", "false"}
    ):
        return None
    return re.sub(r"\s+", " ", value)


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def humanize(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = re.sub(r"[_\-.]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def stable_id(prefix: str, identity: str, limit: int = 128) -> str:
    normalized = identity.replace("\\", ".").replace("/", ".").lower()
    normalized = re.sub(r"\.(xaml|designer\.cs|cshtml|html|htm|cs)$", "", normalized)
    normalized = ID_RE.sub(".", normalized).strip(".")
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    if not normalized:
        normalized = digest
    value = f"{prefix}.{normalized}"
    if len(value) > limit:
        value = f"{value[: limit - 13].rstrip('.')}.{digest}"
    return value


def confidence(level: str, score: float | None) -> dict:
    return {"level": level, "score": score}


def attr_value(attrs: str, name: str) -> str | None:
    pattern = (
        rf"(?<![\w:.-]){re.escape(name)}\s*=\s*"
        rf"(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)')"
    )
    match = re.search(pattern, attrs, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group("double") if match.group("double") is not None else match.group("single")


def root_tag(text: str) -> tuple[str, str]:
    cleaned = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<\?.*?\?>", "", cleaned, flags=re.DOTALL)
    match = re.search(
        r"<(?P<tag>[A-Za-z_][\w:.-]*)(?P<attrs>(?:\"[^\"]*\"|'[^']*'|[^'\">])*)>",
        cleaned,
        flags=re.DOTALL,
    )
    if not match:
        return "unknown", ""
    return match.group("tag"), match.group("attrs")


def project_directory(path: Path, project_dirs: list[Path]) -> Path | None:
    matches = [directory for directory in project_dirs if directory in path.parents]
    return max(matches, key=lambda item: len(item.parts)) if matches else None


def common_prefix_score(left: Path, right: Path) -> int:
    score = 0
    for lpart, rpart in zip(left.parts, right.parts):
        if lpart.lower() != rpart.lower():
            break
        score += 1
    return score


def xaml_disposition(path: Path, tag: str) -> tuple[str, str]:
    relative = path.relative_to(ROOT)
    if relative.parts[0].lower() in EXCLUDED_TOPS:
        return "excluded", "Task/temp/output snapshot is not active product UI."
    stem = path.stem.lower()
    tag_short = tag.split(":")[-1].lower()
    if tag_short in {"resourcedictionary", "application"}:
        return "resource_template", f"Root {tag_short} is application/style resource."
    if any(token in stem for token in ("designtimeresources", "resources", "styles", "theme")):
        return "resource_template", "Named resource/style artifact, not an independently navigated surface."
    if tag_short in {"window", "page", "screenbase"}:
        return "screen", f"Root {tag.split(':')[-1]} is an independently hosted UI surface."
    if stem in {"uibaseform", "customerdisplaycontrol"}:
        return "screen", "Source is a stable application shell/display host."
    if tag_short == "usercontrol" and re.search(r"(dialog|view)$", path.stem, re.I):
        return "screen", "View/dialog UserControl has a stable surface identity."
    if tag_short in {"usercontrol", "usercontrolbase"}:
        return "component", "UserControl is hosted as a component; no standalone Window/ScreenBase root."
    return "resource_template", f"Root {tag} is not a standalone screen type."


def role_actions(control_type: str, attrs: str = "") -> tuple[str, list[str]]:
    value = control_type.split(":")[-1].lower()
    input_type = (attr_value(attrs, "type") or "").lower()
    if value == "input":
        if input_type in {"submit", "button", "reset", "image"}:
            return "button", ["click", "focus"]
        if input_type in {"checkbox"}:
            return "checkbox", ["toggle", "focus"]
        if input_type in {"radio"}:
            return "radio_button", ["select", "focus"]
        if input_type in {"hidden"}:
            return "hidden_field", []
        return "text_field", ["focus", "type_text", "set_value"]
    mappings = (
        (("button", "buttonbase", "hyperlink"), "button", ["click", "focus"]),
        (("textbox", "maskedtextbox", "passwordbox", "textarea"), "text_field", ["focus", "type_text", "set_value"]),
        (("combobox", "select"), "combobox", ["focus", "select", "expand", "collapse"]),
        (("listbox", "listview"), "list_view", ["focus", "select", "scroll"]),
        (("datagrid", "gridview"), "table", ["focus", "select", "scroll"]),
        (("checkbox",), "checkbox", ["focus", "toggle"]),
        (("radiobutton",), "radio_button", ["focus", "select"]),
        (("togglebutton",), "toggle_button", ["focus", "toggle"]),
        (("menuitem",), "menu_item", ["click", "expand", "collapse"]),
        (("menu",), "menu", ["expand", "collapse"]),
        (("tabitem",), "tab", ["select", "focus"]),
        (("treeviewitem",), "tree_item", ["select", "expand", "collapse", "focus"]),
        (("treeview",), "tree", ["select", "expand", "collapse", "scroll"]),
        (("scrollviewer", "scrollbar"), "scroll_area", ["scroll"]),
        (("slider", "numericupdown"), "slider", ["focus", "set_value"]),
        (("label", "textblock", "span", "p", "h1", "h2", "h3", "legend"), "label", []),
        (("image",), "image", []),
        (("link", "a"), "link", ["click", "focus"]),
        (("form",), "form", ["submit"]),
    )
    for names, role, actions in mappings:
        if value in names or any(name in value for name in names):
            return role, actions
    return "component", []


def infer_region(
    screen_type: str,
    source_path: str,
    name: str,
    role: str,
    source_line: int,
    line_count: int,
) -> str:
    combined = f"{source_path} {name}".lower()
    if screen_type in {"dialog", "modal", "popup"}:
        return "modal"
    if "header" in combined or "title" in name.lower():
        return "header"
    if "footer" in combined:
        return "footer"
    if any(token in combined for token in ("toolbar", "functionbutton", "quickbutton", "presetbutton")):
        return "toolbar"
    if any(token in combined for token in ("statusbar", "statuscontrol")):
        return "statusbar"
    if line_count > 0 and source_line / line_count < 0.14:
        return "header"
    if line_count > 0 and source_line / line_count > 0.87:
        return "footer"
    if role in {"menu", "menu_item", "tab"}:
        return "toolbar"
    return "body"


def extract_method_body(text: str, method_name: str) -> tuple[str, int | None]:
    definition = re.search(
        rf"(?m)^\s*(?:(?:public|private|protected|internal|static|async|virtual|override|sealed|new)\s+)*"
        rf"[\w<>,\[\].?]+\s+{re.escape(method_name)}\s*\(",
        text,
    )
    if not definition:
        return "", None
    start = text.find("{", definition.end())
    if start < 0:
        return "", None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1], line_number(text, definition.start())
    return "", line_number(text, definition.start())


def classify_designer(path: Path, text: str) -> tuple[str, str, str]:
    lower_name = path.name.lower()
    if lower_name in {"resources.designer.cs", "settings.designer.cs"}:
        return "excluded", "generated", "Generated resource/settings designer is not UI."
    if "system.windows.forms" not in text and ".controls.add(" not in text.lower():
        return "excluded", "generated", "Typed dataset/non-UI generated Designer file."
    sibling = path.with_name(re.sub(r"\.designer\.cs$", ".cs", path.name, flags=re.I))
    sibling_text = read_text(sibling) if sibling.exists() else ""
    match = re.search(r"class\s+\w+\s*:\s*([^\r\n{]+)", sibling_text)
    bases = match.group(1) if match else ""
    if re.search(r"\bUserControl\b", bases):
        return "component", "winforms_user_control", "WinForms UserControl is hosted by a form/surface."
    return "screen", "form", "WinForms Designer has controls and a Form host."


def screen_type_for(candidate: dict) -> str:
    kind = candidate["kind"]
    root = candidate.get("root_type", "").split(":")[-1].lower()
    stem = Path(candidate["path"]).stem.lower()
    if kind == "winforms":
        return "form"
    if kind in {"razor", "html"}:
        return "page"
    if kind == "code_ui":
        return candidate.get("ui_base", "window").lower()
    if "dialog" in stem:
        return "dialog"
    if root == "window":
        return "window"
    if root == "page":
        return "page"
    if "popup" in stem or "overlay" in stem:
        return "overlay"
    if "display" in stem:
        return "display"
    return "page"


def extract_screen_titles(candidate: dict, text: str) -> tuple[list[str], list[str]]:
    titles: list[str | None] = []
    aliases: list[str | None] = []
    kind = candidate["kind"]
    if kind == "xaml":
        _, attrs = root_tag(text)
        titles.extend(
            [
                literal(attr_value(attrs, "Title")),
                literal(attr_value(attrs, "AutomationProperties.Name")),
            ]
        )
        for match in re.finditer(
            r"<(?:TextBlock|Label)\b(?P<attrs>(?:\"[^\"]*\"|'[^']*'|[^'\">])*)>",
            text,
            flags=re.DOTALL,
        ):
            attrs = match.group("attrs")
            visible = literal(attr_value(attrs, "Text") or attr_value(attrs, "Content"))
            if visible:
                titles.append(visible)
                break
    elif kind == "winforms":
        match = re.search(r"\bthis\.Text\s*=\s*\"([^\"]*)\"", text)
        titles.append(literal(match.group(1)) if match else None)
    else:
        patterns = (
            r"<title[^>]*>(.*?)</title>",
            r"<h1[^>]*>(.*?)</h1>",
            r"(?:ViewBag|ViewData)\.Title\s*=\s*\"([^\"]+)\"",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I | re.S)
            if match:
                titles.append(literal(re.sub(r"<[^>]+>", "", match.group(1))))
    class_short = candidate.get("class_name") or Path(candidate["path"]).stem
    human = humanize(class_short)
    visible_titles = dedupe(titles)
    aliases.extend([class_short, Path(candidate["path"]).stem, human])
    if kind in {"razor", "html"}:
        parts = Path(candidate["path"]).parts
        if "Views" in parts:
            index = parts.index("Views")
            if len(parts) > index + 2:
                aliases.append(f"/{parts[index + 1]}/{Path(parts[index + 2]).stem}")
    elif kind == "xaml":
        _, attrs = root_tag(text)
        aliases.append(attr_value(attrs, "x:Class"))
    return visible_titles, dedupe(aliases)


def add_diagnostic(
    diagnostics: list[dict],
    seen: set[tuple],
    category: str,
    reason: str,
    source_evidence: str | None,
    target_ref: dict | None = None,
    score: float | None = 0.4,
) -> None:
    if category not in DIAGNOSTIC_CATEGORIES:
        raise ValueError(category)
    key = (category, json.dumps(target_ref, sort_keys=True), reason, source_evidence)
    if key in seen:
        return
    seen.add(key)
    identity = "|".join("" if item is None else str(item) for item in key)
    diagnostics.append(
        {
            "diagnostic_id": stable_id("diag", identity),
            "category": category,
            "target_ref": target_ref,
            "reason": reason,
            "confidence": confidence("requires_runtime_verification", score),
            "source_evidence": source_evidence,
        }
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    )
    path.write_bytes(payload.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_revision(candidates: list[dict]) -> str:
    digest = hashlib.sha256()
    for candidate in sorted(candidates, key=lambda item: item["path"].lower()):
        path = ROOT / candidate["path"]
        digest.update(candidate["path"].encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return "tree:" + digest.hexdigest()


def build() -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not SOURCE_UI.exists():
        raise FileNotFoundError(SOURCE_UI)
    source_document = json.loads(read_text(SOURCE_UI))
    source_records = source_document.get("controls", [])
    source_by_file: dict[str, list[dict]] = defaultdict(list)
    for record in source_records:
        source_by_file[record["sourceFile"].lower()].append(record)

    project_dirs = sorted(
        {
            path.parent
            for path in ROOT.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".csproj", ".vbproj"}
            and not is_skipped(path)
        },
        key=lambda path: len(path.parts),
    )
    candidates: list[dict] = []
    candidate_paths: set[str] = set()

    for path in ROOT.rglob("*"):
        if not path.is_file() or is_skipped(path):
            continue
        name_lower = path.name.lower()
        suffix = path.suffix.lower()
        if suffix == ".xaml":
            text = read_text(path)
            tag, attrs = root_tag(text)
            disposition, reason = xaml_disposition(path, tag)
            class_name = (attr_value(attrs, "x:Class") or path.stem).split(".")[-1]
            candidate = {
                "path": rel(path),
                "kind": "xaml",
                "root_type": tag,
                "class_name": class_name,
                "disposition": disposition,
                "reason": reason,
                "evidence": f"{rel(path)}:1 root={tag}",
                "project_dir": project_directory(path, project_dirs),
            }
        elif name_lower.endswith(".designer.cs"):
            text = read_text(path)
            disposition, ui_type, reason = classify_designer(path, text)
            candidate = {
                "path": rel(path),
                "kind": "winforms",
                "root_type": ui_type,
                "class_name": re.sub(r"\.designer\.cs$", "", path.name, flags=re.I),
                "disposition": disposition,
                "reason": reason,
                "evidence": f"{rel(path)}:1 designer={ui_type}",
                "project_dir": project_directory(path, project_dirs),
            }
        elif suffix in {".cshtml", ".html", ".htm"}:
            text = read_text(path)
            top = path.relative_to(ROOT).parts[0].lower()
            if top in EXCLUDED_TOPS:
                disposition = "excluded"
                reason = "Task/temp/output snapshot is not active product UI."
            elif suffix in {".html", ".htm"} and any(
                part.lower() == "doc" for part in path.relative_to(ROOT).parts
            ):
                disposition = "excluded"
                reason = "Generated source/JSDoc documentation page is not product UI."
            elif path.stem.startswith("_"):
                disposition = "component"
                reason = "Partial/layout file is hosted by a Razor/HTML page."
            else:
                disposition = "screen"
                reason = "Razor/HTML document is a stable page surface."
            candidate = {
                "path": rel(path),
                "kind": "razor" if suffix == ".cshtml" else "html",
                "root_type": "page",
                "class_name": path.stem,
                "disposition": disposition,
                "reason": reason,
                "evidence": f"{rel(path)}:1 document={suffix}",
                "project_dir": project_directory(path, project_dirs),
            }
        else:
            continue
        candidates.append(candidate)
        candidate_paths.add(candidate["path"].lower())

    # Add code-only dynamic UI classes that have no XAML/Designer companion.
    ui_class_pattern = re.compile(
        r"(?m)^\s*(?:(?:public|internal|private|protected|sealed|partial|abstract|static)\s+)*"
        r"class\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<bases>[^\r\n{]+)"
    )
    for path in ROOT.rglob("*.cs"):
        if is_skipped(path) or path.name.lower().endswith(".designer.cs"):
            continue
        text = read_text(path)
        for match in ui_class_pattern.finditer(text):
            bases = match.group("bases")
            base_match = re.search(r"\b(Window|Form|Page|Popup|UserControl)\b", bases)
            if not base_match:
                continue
            if (
                (
                    path.name.lower().endswith(".xaml.cs")
                    and path.with_suffix("").exists()
                )
                or
                path.with_suffix(".xaml").exists()
                or (path.parent / f"{path.stem}.Designer.cs").exists()
                or (path.parent / f"{path.stem}.designer.cs").exists()
            ):
                continue
            relative = rel(path)
            identity = f"{relative}#{match.group('name')}"
            if identity.lower() in candidate_paths:
                continue
            top = path.relative_to(ROOT).parts[0].lower()
            ui_base = base_match.group(1)
            if top in EXCLUDED_TOPS:
                disposition = "excluded"
                reason = "Task/temp snapshot is not active product UI."
            elif match.group("name").lower().endswith("base") or "abstract" in match.group(0):
                disposition = "resource_template"
                reason = "Code-only abstract/base UI type supplies shared behavior, not an instance surface."
            elif ui_base == "UserControl":
                disposition = "component"
                reason = "Code-only UserControl is hosted as a component."
            else:
                disposition = "dynamic_diagnostic"
                reason = "Code-only UI surface requires runtime construction/calibration."
            candidates.append(
                {
                    "path": relative,
                    "identity": identity,
                    "kind": "code_ui",
                    "root_type": ui_base,
                    "ui_base": ui_base,
                    "class_name": match.group("name"),
                    "source_line": line_number(text, match.start()),
                    "disposition": disposition,
                    "reason": reason,
                    "evidence": f"{relative}:{line_number(text, match.start())} base={ui_base}",
                    "project_dir": project_directory(path, project_dirs),
                }
            )

    screens: list[dict] = []
    screen_candidate_by_path: dict[str, dict] = {}
    screen_ids_by_name: dict[str, list[str]] = defaultdict(list)
    screen_candidates: list[dict] = []
    diagnostics: list[dict] = []
    diagnostic_seen: set[tuple] = set()

    for candidate in candidates:
        if candidate["disposition"] not in {"screen", "dynamic_diagnostic"}:
            continue
        identity = candidate.get("identity", candidate["path"])
        screen_id = stable_id("screen", identity)
        candidate["screen_id"] = screen_id
        screen_type = screen_type_for(candidate)
        candidate["screen_type"] = screen_type
        text = read_text(ROOT / candidate["path"])
        titles, aliases = extract_screen_titles(candidate, text)
        name = humanize(candidate["class_name"]) or Path(candidate["path"]).stem
        # Aliases are evidence-backed lookup keys. They may intentionally equal a
        # display name; the contract only forbids duplicates inside the alias list.
        level = (
            "requires_runtime_verification"
            if candidate["disposition"] == "dynamic_diagnostic"
            else "statically_inferred"
        )
        score = 0.45 if level == "requires_runtime_verification" else 0.86
        screens.append(
            {
                "screen_id": screen_id,
                "name": name,
                "screen_type": screen_type,
                "visible_titles": dedupe(titles),
                "aliases": dedupe(aliases),
                "parent_screen_id": None,
                "source_evidence": candidate["evidence"],
                "confidence": confidence(level, score),
                "metadata": {
                    "source_path": candidate["path"],
                    "framework": candidate["kind"],
                    "runtime_verified": False,
                },
            }
        )
        screen_candidate_by_path[candidate["path"].lower()] = candidate
        screen_candidates.append(candidate)
        screen_ids_by_name[candidate["class_name"].lower()].append(screen_id)
        screen_ids_by_name[Path(candidate["path"]).stem.lower()].append(screen_id)
        if level == "requires_runtime_verification":
            add_diagnostic(
                diagnostics,
                diagnostic_seen,
                "unconfirmed_screen",
                "Code-only/dynamic surface was found statically but not instantiated in an authorized test runtime.",
                candidate["evidence"],
                {"screen_id": screen_id},
                0.45,
            )

    # Map shared components to every statically evidenced host (M:N), then materialize
    # host-specific component instances so IDs and relationships cannot leak across hosts.
    by_screen_id = {candidate["screen_id"]: candidate for candidate in screen_candidates}
    component_instances: list[dict] = []
    for candidate in list(candidates):
        if candidate["disposition"] != "component":
            continue
        path = ROOT / candidate["path"]
        same_project = [
            screen
            for screen in screen_candidates
            if candidate["project_dir"] is not None
            and screen["project_dir"] == candidate["project_dir"]
        ]
        pool = same_project or screen_candidates
        if not pool:
            candidate["disposition"] = "excluded"
            candidate["reason"] = "No indexed host screen exists for this component."
            continue

        def host_score(screen: dict) -> tuple[int, int, int, int]:
            screen_path = ROOT / screen["path"]
            screen_text = read_text(screen_path)
            referenced = bool(
                re.search(
                    rf"\b{re.escape(candidate['class_name'])}\b",
                    screen_text,
                    flags=re.I,
                )
            )
            primary = bool(
                screen["class_name"].lower() in {"mainwindow", "uibaseform"}
                or (
                    screen["class_name"].lower().endswith("view")
                    and screen["screen_type"] not in {"dialog", "overlay"}
                )
            )
            project_depth = (
                len(screen_path.relative_to(screen["project_dir"]).parts)
                if screen.get("project_dir")
                else len(screen_path.parts)
            )
            return (
                1 if referenced else 0,
                1 if primary else 0,
                common_prefix_score(path, screen_path),
                -project_depth,
            )

        explicit_hosts: list[dict] = []
        component_stem = Path(candidate["path"]).stem
        for screen in pool:
            screen_path = ROOT / screen["path"]
            screen_text = read_text(screen_path)
            referenced = bool(re.search(
                rf"(?:\b{re.escape(candidate['class_name'])}\b|"
                rf"['\"]{re.escape(component_stem)}['\"])",
                screen_text, flags=re.I,
            ))
            # Razor side menus are selected dynamically through ViewData.
            if candidate["kind"] == "razor" and component_stem.lower() in {
                "_backofficesidemenu", "_callcentersidemenu"
            }:
                controller = component_stem.strip("_").replace("SideMenu", "")
                referenced = f"\\Views\\{controller}\\".lower() in screen["path"].lower()
            if candidate["kind"] == "razor" and component_stem.lower() in {
                "_layout", "_viewstart"
            }:
                referenced = screen["kind"] == "razor"
            if referenced:
                explicit_hosts.append(screen)
        hosts = explicit_hosts or [max(pool, key=host_score)]
        hosts = sorted({host["screen_id"]: host for host in hosts}.values(),
                       key=lambda item: item["screen_id"])
        host = hosts[0]
        candidate["mapped_screen_ids"] = [item["screen_id"] for item in hosts]
        candidate["mapped_screen_id"] = host["screen_id"]
        candidate["reason"] += (
            " Hosts resolved by explicit source reference/project boundary: "
            + ", ".join(item["path"] for item in hosts) + "."
        )
        for extra_host in hosts[1:]:
            instance = dict(candidate)
            instance["mapped_screen_id"] = extra_host["screen_id"]
            instance["identity"] = (
                candidate.get("identity", candidate["path"])
                + "#host=" + extra_host["screen_id"]
            )
            instance["_component_instance"] = True
            component_instances.append(instance)
        if not same_project:
            add_diagnostic(
                diagnostics,
                diagnostic_seen,
                "unconfirmed_element",
                "Component host is outside its project boundary and requires runtime verification.",
                candidate["evidence"],
                {"screen_id": host["screen_id"]},
                0.3,
            )
    candidates.extend(component_instances)

    screen_record_by_id = {screen["screen_id"]: screen for screen in screens}

    # Parent screens for dialog/display surfaces are inferred only within the same project.
    for candidate in screen_candidates:
        if candidate["screen_type"] not in {"dialog", "overlay", "display"}:
            continue
        hosts = [
            other
            for other in screen_candidates
            if other["screen_id"] != candidate["screen_id"]
            and other["project_dir"] == candidate["project_dir"]
            and other["screen_type"] not in {"dialog", "overlay"}
        ]
        if hosts:
            host = max(
                hosts,
                key=lambda other: common_prefix_score(
                    ROOT / candidate["path"], ROOT / other["path"]
                ),
            )
            screen_record_by_id[candidate["screen_id"]]["parent_screen_id"] = host["screen_id"]

    elements: list[dict] = []
    element_keys: set[str] = set()
    element_source_meta: dict[str, dict] = {}
    component_element_ids: dict[tuple[str, str], str] = {}

    def unique_element_id(base: str, identity: str) -> str:
        value = stable_id("el", base)
        if value not in element_keys:
            element_keys.add(value)
            return value
        value = stable_id("el", base + "." + hashlib.sha256(identity.encode()).hexdigest()[:10])
        counter = 2
        while value in element_keys:
            value = stable_id("el", base + f".{counter}")
            counter += 1
        element_keys.add(value)
        return value

    # Represent each mapped component as a stable parent element.
    for candidate in candidates:
        if candidate["disposition"] != "component" or not candidate.get("mapped_screen_id"):
            continue
        identity = candidate.get("identity", candidate["path"])
        element_id = unique_element_id(
            f"{candidate['mapped_screen_id']}.component.{identity}", identity
        )
        component_element_ids[(candidate["path"].lower(), candidate["mapped_screen_id"])] = element_id
        name = humanize(candidate["class_name"]) or Path(candidate["path"]).stem
        screen_type = screen_record_by_id[candidate["mapped_screen_id"]]["screen_type"]
        region = infer_region(
            screen_type, candidate["path"], name, "component", 1, 1
        )
        elements.append(
            {
                "element_id": element_id,
                "screen_id": candidate["mapped_screen_id"],
                "parent_element_id": None,
                "name": name,
                "role": "component",
                "visible_texts": [],
                "aliases": dedupe([candidate["class_name"], Path(candidate["path"]).stem]),
                "supported_actions": [],
                "state_conditions": {
                    "visible_when": "host layout/template selects this component"
                },
                "region": region,
                "normalized_bounds": None,
                "anchors": [],
                "neighbors": [],
                "expected_effects": [],
                "source_evidence": candidate["evidence"],
                "confidence": confidence("statically_inferred", 0.78),
                "metadata": {
                    "source_path": candidate["path"],
                    "component_host": candidate["mapped_screen_id"],
                },
            }
        )
        element_source_meta[element_id] = {
            "source_path": candidate["path"],
            "source_line": 1,
            "attrs": "",
            "handler": None,
            "command": None,
            "business_candidates": [],
        }

    # Parse all meaningful XAML tags, including unnamed visible/interactive controls.
    tag_pattern = re.compile(
        r"<(?P<tag>[A-Za-z_][\w:.-]*)(?P<attrs>(?:\"[^\"]*\"|'[^']*'|[^'\">])*)/?>",
        flags=re.DOTALL,
    )
    structural_tags = {
        "grid",
        "stackpanel",
        "dockpanel",
        "wrappanel",
        "canvas",
        "border",
        "rowdefinition",
        "columndefinition",
        "resourcedictionary",
        "style",
        "setter",
        "trigger",
        "datatrigger",
        "controltemplate",
        "datatemplate",
    }
    source_lookup: dict[tuple[str, int, str], dict] = {}
    for source_path, records in source_by_file.items():
        for record in records:
            source_lookup[
                (
                    source_path,
                    int(record.get("sourceLine") or 0),
                    (record.get("sourceName") or "").lower(),
                )
            ] = record

    for candidate in candidates:
        if candidate["kind"] != "xaml" or candidate["disposition"] not in {"screen", "component"}:
            continue
        screen_id = candidate.get("screen_id") or candidate.get("mapped_screen_id")
        if not screen_id:
            continue
        path = ROOT / candidate["path"]
        text = read_text(path)
        lines = text.count("\n") + 1
        parent_id = component_element_ids.get((candidate["path"].lower(), screen_id))
        for occurrence, match in enumerate(tag_pattern.finditer(text)):
            tag = match.group("tag")
            attrs = match.group("attrs")
            tag_short = tag.split(":")[-1]
            if tag_short.lower() in structural_tags:
                continue
            source_name = (
                attr_value(attrs, "AutomationProperties.AutomationId")
                or attr_value(attrs, "x:Name")
                or attr_value(attrs, "Name")
            )
            visible = literal(
                attr_value(attrs, "AutomationProperties.Name")
                or attr_value(attrs, "Content")
                or attr_value(attrs, "Text")
                or attr_value(attrs, "Header")
                or attr_value(attrs, "ToolTip")
            )
            role, actions = role_actions(tag_short, attrs)
            command = attr_value(attrs, "Command")
            event_bindings = [
                (event, attr_value(attrs, event))
                for event in EVENT_NAMES
                if attr_value(attrs, event)
            ]
            interactive = bool(actions or command or event_bindings)
            semantic = role in {"label", "image", "table", "list_view"} and bool(
                visible or source_name
            )
            if not source_name and not visible and not interactive and not semantic:
                continue
            source_line = line_number(text, match.start())
            nearby = re.sub(r"\s+", " ", match.group(0)).strip()
            identity = (
                source_name
                or f"{candidate['path']}|{tag_short}|{hashlib.sha256(nearby.encode('utf-8')).hexdigest()[:12]}"
            )
            element_id = unique_element_id(
                f"{screen_id}.{source_name or identity}", f"{candidate['path']}:{source_line}:{occurrence}"
            )
            lookup = source_lookup.get(
                (candidate["path"].lower(), source_line, (source_name or "").lower())
            )
            if lookup is None:
                lookup = source_lookup.get((candidate["path"].lower(), source_line, ""))
            handler = (
                (lookup or {}).get("eventHandler")
                or (event_bindings[0][1] if event_bindings else None)
            )
            command = (lookup or {}).get("command") or command
            business = list((lookup or {}).get("businessCallCandidates") or [])
            state: dict[str, str | bool | int] = {}
            for attr, key in (
                ("Visibility", "visible_when"),
                ("IsEnabled", "enabled_when"),
                ("IsChecked", "checked_when"),
                ("IsSelected", "selected_when"),
                ("IsReadOnly", "read_only_when"),
                ("MaxLength", "max_length"),
            ):
                value = attr_value(attrs, attr)
                if value is not None:
                    state[key] = value
            if interactive:
                state.setdefault("visible_when", "source default visibility")
                state.setdefault("enabled_when", "source default enabled state")
            expected: list[str] = []
            if handler:
                expected.append(f"invoke source handler {handler}")
            if command:
                expected.append(f"execute source command {command}")
            expected.extend(f"candidate call {call}" for call in business)
            screen_type = screen_record_by_id[screen_id]["screen_type"]
            region = infer_region(
                screen_type,
                candidate["path"],
                source_name or visible or tag_short,
                role,
                source_line,
                lines,
            )
            elements.append(
                {
                    "element_id": element_id,
                    "screen_id": screen_id,
                    "parent_element_id": parent_id,
                    "name": humanize(source_name or visible or tag_short),
                    "role": role,
                    "visible_texts": dedupe([visible]),
                    "aliases": dedupe([
                        source_name,
                        attr_value(attrs, "AutomationProperties.AutomationId"),
                        attr_value(attrs, "AutomationProperties.Name"),
                        command,
                        handler,
                    ]),
                    "supported_actions": dedupe(actions),
                    "state_conditions": state,
                    "region": region,
                    "normalized_bounds": None,
                    "anchors": [],
                    "neighbors": [],
                    "expected_effects": dedupe(expected),
                    "source_evidence": f"{candidate['path']}:{source_line}",
                    "confidence": confidence("statically_inferred", 0.82 if source_name else 0.68),
                    "metadata": {
                        "source_path": candidate["path"],
                        "source_line": source_line,
                        "source_control_type": tag_short,
                        "stable_locator": source_name,
                        "runtime_verified": False,
                    },
                }
            )
            element_source_meta[element_id] = {
                "source_path": candidate["path"],
                "source_line": source_line,
                "attrs": attrs,
                "handler": handler,
                "command": command,
                "business_candidates": business,
            }

    # WinForms controls come from the mandated source mapping script.
    for source_path, records in source_by_file.items():
        candidate = next(
            (
                item
                for item in candidates
                if item["path"].lower() == source_path and item["kind"] == "winforms"
            ),
            None,
        )
        if not candidate or candidate["disposition"] not in {"screen", "component"}:
            continue
        screen_id = candidate.get("screen_id") or candidate.get("mapped_screen_id")
        if not screen_id:
            continue
        parent_id = component_element_ids.get((candidate["path"].lower(), screen_id))
        text = read_text(ROOT / candidate["path"])
        lines = text.count("\n") + 1
        for record in records:
            source_name = record.get("automationId") or record.get("sourceName")
            if not source_name:
                continue
            role, actions = role_actions(record.get("controlType") or "component")
            visible = literal(record.get("name"))
            handler = record.get("eventHandler")
            business = list(record.get("businessCallCandidates") or [])
            source_line = int(record.get("sourceLine") or 1)
            element_id = unique_element_id(
                f"{screen_id}.{source_name}",
                f"{candidate['path']}:{source_line}:{source_name}",
            )
            expected = dedupe(
                ([f"invoke source handler {handler}"] if handler else [])
                + [f"candidate call {call}" for call in business]
            )
            elements.append(
                {
                    "element_id": element_id,
                    "screen_id": screen_id,
                    "parent_element_id": parent_id,
                    "name": humanize(source_name),
                    "role": role,
                    "visible_texts": dedupe([visible]),
                    "aliases": dedupe([source_name, record.get("automationId"), handler]),
                    "supported_actions": actions,
                    "state_conditions": (
                        {
                            "visible_when": "WinForms designer/default runtime visibility",
                            "enabled_when": "WinForms designer/default runtime enabled state",
                        }
                        if actions
                        else {}
                    ),
                    "region": infer_region(
                        screen_record_by_id[screen_id]["screen_type"],
                        candidate["path"],
                        source_name,
                        role,
                        source_line,
                        lines,
                    ),
                    "normalized_bounds": None,
                    "anchors": [],
                    "neighbors": [],
                    "expected_effects": expected,
                    "source_evidence": f"{candidate['path']}:{source_line}",
                    "confidence": confidence("statically_inferred", 0.84),
                    "metadata": {
                        "source_path": candidate["path"],
                        "source_line": source_line,
                        "source_control_type": record.get("controlType"),
                        "stable_locator": source_name,
                        "runtime_verified": False,
                    },
                }
            )
            element_source_meta[element_id] = {
                "source_path": candidate["path"],
                "source_line": source_line,
                "attrs": "",
                "handler": handler,
                "command": None,
                "business_candidates": business,
            }

    # Parse Razor/HTML semantic and interactive controls.
    html_tag_pattern = re.compile(
        r"<(?P<tag>input|button|select|textarea|a|form|label|h1|h2|h3|legend|p|span)\b"
        r"(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>"
        r"|<(?P<void>input)\b(?P<voidattrs>[^>]*)/?>",
        flags=re.I | re.S,
    )
    for candidate in candidates:
        if candidate["kind"] not in {"razor", "html"} or candidate["disposition"] not in {"screen", "component"}:
            continue
        screen_id = candidate.get("screen_id") or candidate.get("mapped_screen_id")
        if not screen_id:
            continue
        text = read_text(ROOT / candidate["path"])
        lines = text.count("\n") + 1
        parent_id = component_element_ids.get((candidate["path"].lower(), screen_id))
        for occurrence, match in enumerate(html_tag_pattern.finditer(text)):
            tag = (match.group("tag") or match.group("void") or "").lower()
            attrs = match.group("attrs") or match.group("voidattrs") or ""
            body = re.sub(r"<[^>]+>", " ", match.group("body") or "")
            source_name = (
                attr_value(attrs, "data-automation-id")
                or attr_value(attrs, "id")
                or attr_value(attrs, "name")
            )
            visible = literal(
                attr_value(attrs, "aria-label")
                or attr_value(attrs, "value")
                or re.sub(r"\s+", " ", body)
            )
            role, actions = role_actions(tag, attrs)
            if tag in {"label", "h1", "h2", "h3", "legend", "p", "span"} and not visible:
                continue
            if not source_name and not visible and not actions:
                continue
            source_line = line_number(text, match.start())
            nearby = re.sub(r"\s+", " ", match.group(0)).strip()
            identity = source_name or (
                f"{candidate['path']}|{tag}|"
                f"{hashlib.sha256(nearby.encode('utf-8')).hexdigest()[:12]}"
            )
            element_id = unique_element_id(
                f"{screen_id}.{identity}",
                f"{candidate['path']}:{source_line}:{occurrence}",
            )
            state: dict[str, str | bool] = {}
            for attribute, key in (
                ("required", "required"),
                ("disabled", "disabled"),
                ("readonly", "read_only"),
                ("checked", "checked"),
                ("selected", "selected"),
            ):
                if re.search(rf"\b{attribute}\b", attrs, flags=re.I):
                    state[key] = True
            if actions:
                state.setdefault("visible_when", "document/source layout renders this element")
                state.setdefault("enabled_when", "HTML source/default enabled state")
            expected: list[str] = []
            destination = attr_value(attrs, "href") or attr_value(attrs, "action")
            asp_action = attr_value(attrs, "asp-action")
            asp_controller = attr_value(attrs, "asp-controller")
            asp_route = attr_value(attrs, "asp-route")
            onclick = attr_value(attrs, "onclick")
            if not destination and asp_action:
                destination = f"/{asp_controller or ''}/{asp_action}"
            if not destination and asp_route:
                destination = asp_route
            if not destination and onclick:
                direct_js = re.search(
                    r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]"
                    r"|window\.open\(\s*['\"]([^'\"]+)['\"]",
                    onclick, flags=re.I,
                )
                if direct_js:
                    destination = direct_js.group(1) or direct_js.group(2)
            if destination:
                expected.append(f"request/navigate to {destination}")
            elements.append(
                {
                    "element_id": element_id,
                    "screen_id": screen_id,
                    "parent_element_id": parent_id,
                    "name": humanize(source_name or visible or tag),
                    "role": role,
                    "visible_texts": dedupe([visible]),
                    "aliases": dedupe([source_name, attr_value(attrs, "aria-label")]),
                    "supported_actions": actions,
                    "state_conditions": state,
                    "region": infer_region(
                        screen_record_by_id[screen_id]["screen_type"],
                        candidate["path"],
                        source_name or visible or tag,
                        role,
                        source_line,
                        lines,
                    ),
                    "normalized_bounds": None,
                    "anchors": [],
                    "neighbors": [],
                    "expected_effects": expected,
                    "source_evidence": f"{candidate['path']}:{source_line}",
                    "confidence": confidence("statically_inferred", 0.72),
                    "metadata": {
                        "source_path": candidate["path"],
                        "source_line": source_line,
                        "source_control_type": tag,
                        "stable_locator": source_name,
                        "runtime_verified": False,
                        "static_destination": destination,
                        "onclick": onclick,
                    },
                }
            )
            element_source_meta[element_id] = {
                "source_path": candidate["path"],
                "source_line": source_line,
                "attrs": attrs,
                "handler": None,
                "command": None,
                "business_candidates": [],
                "static_destination": destination,
            }

    # Materialize the data-driven WinPOS MainMenu buttons. The runtime path is:
    # CurrentPageButtons -> Button.Tag(MenuButtonRow) -> GrdMenuButtons_Click ->
    # UIPOSLibrary.AcceptEvent(EventCode). Numeric codes are resolved from EventCodes.cs.
    event_code_text = read_text(ROOT / "Source" / "Common" / "Common.Const" / "EventCodes.cs")
    event_names_by_code = {
        int(match.group("code")): match.group("name")
        for match in re.finditer(
            r"EventCode\s+(?P<name>[A-Za-z_]\w*)\s*\{[^=]*=\s*"
            r"new\s+EventCode\([^,]+,\s*(?P<code>\d+)\)",
            event_code_text,
        )
    }
    main_menu_candidates = [
        item for item in screen_candidates
        if item["class_name"].lower() == "mainmenuview"
    ]
    if main_menu_candidates:
        main_menu = main_menu_candidates[0]
        main_screen_id = main_menu["screen_id"]
        menu_xml_files = sorted(
            (ROOT / "Source" / "POS4U" / "Settings").glob("MainMenuList*.xml")
        )
        button_pattern = re.compile(r"<MenuButton>(?P<body>.*?)</MenuButton>", re.S)
        for xml_path in menu_xml_files:
            xml_text = read_text(xml_path)
            for occurrence, match in enumerate(button_pattern.finditer(xml_text)):
                body = match.group("body")
                values = {
                    key: (found.group(1).strip() if found else "")
                    for key in (
                        "MenuNumber", "PageNumber", "ButtonNumber", "Description",
                        "ButtonType", "EventCode", "InputData", "AddInfos",
                    )
                    for found in [re.search(rf"<{key}>(.*?)</{key}>", body, re.S)]
                }
                if values["ButtonType"] != "1" or not values["EventCode"].isdigit():
                    continue
                code = int(values["EventCode"])
                event_name = event_names_by_code.get(code)
                prefix = event_name.split("_", 1)[0] if event_name and "_" in event_name else None
                target_ids = dedupe(
                    screen_ids_by_name.get(f"{prefix}View".lower(), []) if prefix else []
                )
                target_id = target_ids[0] if len(target_ids) == 1 else None
                source_line = line_number(xml_text, match.start())
                identity = (
                    f"{rel(xml_path)}|{values['MenuNumber']}|{values['PageNumber']}|"
                    f"{values['ButtonNumber']}|{code}|{occurrence}"
                )
                element_id = unique_element_id(
                    f"{main_screen_id}.menu.{identity}", identity
                )
                description = literal(values["Description"])
                effects = [
                    "MainMenuData.CurrentPageButtons supplies MenuButtonRow",
                    "GrdMenuButtons_Click dispatches MenuButtonRow.EventCode",
                ]
                if event_name:
                    effects.append(f"dispatch EventCodes.{event_name}")
                elements.append(
                    {
                        "element_id": element_id,
                        "screen_id": main_screen_id,
                        "parent_element_id": None,
                        "name": humanize(event_name or description or f"Event {code}"),
                        "role": "button",
                        "visible_texts": dedupe([description]),
                        "aliases": dedupe([
                            description, event_name, str(code),
                            f"menu-{values['MenuNumber']}-page-{values['PageNumber']}"
                            f"-button-{values['ButtonNumber']}",
                        ]),
                        "supported_actions": ["click", "focus"],
                        "state_conditions": {
                            "visible_when": (
                                f"menu={values['MenuNumber']} and page={values['PageNumber']}"
                            ),
                            "enabled_when": "MainMenuView.UpdatePageInfo enables this MenuButtonRow",
                        },
                        "region": "body",
                        "normalized_bounds": None,
                        "anchors": [],
                        "neighbors": [],
                        "expected_effects": effects,
                        "source_evidence": f"{rel(xml_path)}:{source_line}",
                        "confidence": confidence("statically_inferred", 0.84),
                        "metadata": {
                            "source_path": rel(xml_path),
                            "source_line": source_line,
                            "source_control_type": "MainMenuDataSet.MenuButtonRow",
                            "stable_locator": identity,
                            "runtime_verified": False,
                            "event_code": code,
                            "event_name": event_name,
                            "target_candidates": target_ids,
                        },
                    }
                )
                element_source_meta[element_id] = {
                    "source_path": rel(xml_path),
                    "source_line": source_line,
                    "attrs": "",
                    "handler": "GrdMenuButtons_Click",
                    "command": event_name,
                    "business_candidates": ["UIPOSLibrary.AcceptEvent"],
                    "static_target_screen_id": target_id,
                    "target_candidates": target_ids,
                    "event_code": code,
                    "event_name": event_name,
                }

    element_by_id = {element["element_id"]: element for element in elements}

    # Add static parent-neighbor and anchor evidence without inventing geometry.
    source_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for element_id, metadata in element_source_meta.items():
        source_groups[
            (element_by_id[element_id]["screen_id"], metadata["source_path"].lower())
        ].append(element_id)
    for ids in source_groups.values():
        ids.sort(key=lambda item: (element_source_meta[item]["source_line"], item))
        for index, element_id in enumerate(ids):
            element = element_by_id[element_id]
            neighbors: list[dict] = []
            if index > 0:
                neighbors.append({"direction": "up", "element_id": ids[index - 1]})
            if index + 1 < len(ids):
                neighbors.append({"direction": "down", "element_id": ids[index + 1]})
            element["neighbors"] = neighbors
            for prior_id in reversed(ids[max(0, index - 4) : index]):
                prior = element_by_id[prior_id]
                if prior["visible_texts"] and prior["role"] == "label":
                    element["anchors"] = [prior_id]
                    break

    def choose_target(target_name: str, source_path: str) -> str | None:
        ids = dedupe(screen_ids_by_name.get(target_name.lower(), []))
        if not ids:
            return None
        source = ROOT / source_path
        return max(
            ids,
            key=lambda screen_id: common_prefix_score(
                source, ROOT / by_screen_id[screen_id]["path"]
            ),
        )

    route_screens: dict[tuple[str, str], str] = {}
    for candidate in screen_candidates:
        parts = Path(candidate["path"]).parts
        if "Views" not in parts:
            continue
        index = parts.index("Views")
        if len(parts) <= index + 2:
            continue
        route_screens[
            (parts[index + 1].lower(), Path(parts[index + 2]).stem.lower())
        ] = candidate["screen_id"]

    def host_controller(screen_id: str) -> str | None:
        parts = Path(by_screen_id[screen_id]["path"]).parts
        if "Views" in parts:
            index = parts.index("Views")
            if len(parts) > index + 1:
                return parts[index + 1]
        return None

    def resolve_web_destination(expression: str | None, screen_id: str) -> tuple[str | None, str]:
        if not expression:
            return None, "no destination expression"
        value = html.unescape(expression).strip()
        controller = host_controller(screen_id)
        action = None
        # Literal URLs and controller/action strings.
        literal_match = re.search(r"(?:^|['\"])(?:https?://[^/]+)?/?"
                                  r"(?P<controller>[A-Za-z_]\w*)/"
                                  r"(?P<action>[A-Za-z_]\w*)", value)
        if literal_match:
            controller = literal_match.group("controller")
            action = literal_match.group("action")
        # Url.Action(action[, controller]); one-argument constants remain relative
        # to the current host controller even when the shared partial names a base class.
        url_match = re.search(r"Url\.Action\((?P<args>.*?)\)", value, flags=re.I | re.S)
        if url_match:
            args = [item.strip() for item in url_match.group("args").split(",")]
            if args:
                quoted = re.search(r"['\"]([^'\"]+)['\"]", args[0])
                token = quoted.group(1) if quoted else args[0].split(".")[-1]
                token = token.strip(" )'")
                if "/" in token:
                    first, second, *_ = token.split("/") + [None]
                    if second:
                        action = first
                else:
                    action = token
            if len(args) > 1:
                quoted_controller = re.search(r"['\"]([^'\"]+)['\"]", args[1])
                if quoted_controller:
                    controller = quoted_controller.group(1).removesuffix("Controller")
                elif "ControllersRoutePrefixes." in args[1]:
                    controller = args[1].split(".")[-1].strip(" )")
        if not action and value not in {"#", "/", ""}:
            clean = value.split("?")[0].rstrip("/").split("/")[-1]
            action = Path(clean).stem
        key = ((controller or "").lower(), (action or "").lower())
        target = route_screens.get(key)
        if target:
            return target, f"resolved route {controller}/{action}"
        candidates = sorted(
            f"{c}/{a}" for c, a in route_screens
            if a == (action or "").lower()
        )
        return None, (
            f"unresolved route expression={value!r}; controller={controller!r}; "
            f"action={action!r}; candidates={candidates[:8]}"
        )

    transitions: list[dict] = []
    transition_keys: set[str] = set()
    unresolved_by_screen: dict[str, list[str]] = defaultdict(list)

    for element in elements:
        metadata = element_source_meta.get(element["element_id"], {})
        if not element["supported_actions"]:
            continue
        handler = metadata.get("handler")
        command = metadata.get("command")
        business = metadata.get("business_candidates") or []
        destination_hint = metadata.get("static_destination")
        body = ""
        handler_line = None
        source_path = metadata.get("source_path")
        if handler and source_path:
            source_file = ROOT / source_path
            if source_file.name.lower().endswith(".designer.cs"):
                code_path = source_file.with_name(
                    re.sub(r"\.designer\.cs$", ".cs", source_file.name, flags=re.I)
                )
            elif source_file.suffix.lower() == ".xaml":
                code_path = Path(str(source_file) + ".cs")
            else:
                code_path = source_file
            if code_path.exists():
                body, handler_line = extract_method_body(read_text(code_path), handler)
        target_id = metadata.get("static_target_screen_id")
        transition_type = "state_change"
        evidence_parts = [element["source_evidence"]]
        if target_id:
            transition_type = "replace"
            evidence_parts.append(
                "Source\\WinPOS\\UI\\WinPOS.UI.MainMenuView\\WinPOS.UI.MainMenuView"
                "\\MainMenuView.xaml.cs:194 handler=GrdMenuButtons_Click"
            )
        if body:
            targets = re.findall(
                r"\bnew\s+([A-Za-z_]\w*(?:Window|Dialog|Form|View|Popup))\s*\(",
                body,
            )
            for target in targets:
                target_id = choose_target(target, source_path)
                if target_id:
                    break
            if target_id:
                target_type = screen_record_by_id[target_id]["screen_type"]
                transition_type = (
                    "modal"
                    if target_type in {"dialog", "modal"} or ".ShowDialog(" in body
                    else ("overlay" if target_type in {"overlay", "popup"} else "replace")
                )
                evidence_parts.append(
                    f"{source_path}.cs:{handler_line or metadata.get('source_line')} handler={handler}"
                )
            elif targets:
                unresolved_by_screen[element["screen_id"]].extend(targets)
        route_reason = ""
        if not target_id and destination_hint:
            target_id, route_reason = resolve_web_destination(
                destination_hint, element["screen_id"]
            )
            if target_id:
                transition_type = "replace"
                evidence_parts.append(route_reason)
        if not target_id and command:
            command_text = re.sub(r"[{}]", " ", command)
            for name in screen_ids_by_name:
                if name.lower() in command_text.lower():
                    target_id = choose_target(name, source_path)
                    if target_id:
                        transition_type = "replace"
                        break

        navigation_semantics = bool(destination_hint) or bool(re.search(
            r"(Url\.Action|window\.location|location\.href|Redirect(?:ToAction)?|"
            r"\.ShowDialog\s*\(|\.Show\s*\(|Content\s*=|Navigate\s*\()",
            body or "", flags=re.I,
        ))
        if target_id is None and navigation_semantics:
            add_diagnostic(
                diagnostics,
                diagnostic_seen,
                "uncertain_transition",
                (
                    f"Navigation was not emitted as a self transition. handler={handler!r}; "
                    f"route={destination_hint!r}; {route_reason or 'no unique static target'}"
                ),
                element["source_evidence"],
                {"element_id": element["element_id"]},
                0.35,
            )
            continue
        if target_id is None and metadata.get("event_code") is not None:
            add_diagnostic(
                diagnostics,
                diagnostic_seen,
                "uncertain_transition",
                (
                    "MainMenu event target is not unique; "
                    f"event={metadata.get('event_name')!r}; "
                    f"code={metadata.get('event_code')}; "
                    f"candidates={metadata.get('target_candidates') or []}; "
                    "handler=GrdMenuButtons_Click"
                ),
                element["source_evidence"],
                {"element_id": element["element_id"]},
                0.4,
            )
            continue

        # Non-navigation, source-wired interactions remain valid in-screen state changes.
        source_wired = bool(handler or command or business or destination_hint)
        if target_id is None and source_wired:
            target_id = element["screen_id"]
            transition_type = "state_change"
        if target_id is None:
            continue
        action = element["supported_actions"][0]
        base = (
            f"{element['screen_id']}.{element['element_id']}.{action}.{target_id}."
            f"{transition_type}"
        )
        transition_id = stable_id("tr", base)
        if transition_id in transition_keys:
            continue
        transition_keys.add(transition_id)
        expected_visible = list(screen_record_by_id[target_id]["visible_titles"])
        expected_hidden = (
            list(screen_record_by_id[element["screen_id"]]["visible_titles"])
            if transition_type == "replace" and target_id != element["screen_id"]
            else []
        )
        transitions.append(
            {
                "transition_id": transition_id,
                "from_screen_id": element["screen_id"],
                "trigger_element_id": element["element_id"],
                "trigger_action": action,
                "guards": (
                    [{"element_id": element["element_id"], "condition": "enabled"}]
                    if action in {"click", "select", "toggle", "submit"}
                    else []
                ),
                "to_screen_id": target_id,
                "transition_type": transition_type,
                "expected_visible": dedupe(expected_visible),
                "expected_hidden": dedupe(expected_hidden),
                "expected_state_changes": dedupe(element["expected_effects"]),
                "source_evidence": "; ".join(dedupe(evidence_parts)),
                "confidence": confidence(
                    "statically_inferred", 0.76 if target_id != element["screen_id"] else 0.62
                ),
            }
        )
        if target_id != element["screen_id"]:
            element["expected_effects"] = dedupe(
                element["expected_effects"]
                + [f"navigate/open {screen_record_by_id[target_id]['name']}"]
            )

    transition_by_id = {transition["transition_id"]: transition for transition in transitions}
    outgoing: dict[str, list[dict]] = defaultdict(list)
    for transition in transitions:
        if transition["to_screen_id"] != transition["from_screen_id"]:
            outgoing[transition["from_screen_id"]].append(transition)

    flows: list[dict] = []
    flow_keys: set[str] = set()
    for first in sorted(
        [item for item in transitions if item["to_screen_id"] != item["from_screen_id"]],
        key=lambda item: item["transition_id"],
    ):
        second_candidates = [
            item
            for item in outgoing.get(first["to_screen_id"], [])
            if item["to_screen_id"] != first["from_screen_id"]
        ]
        steps = [{"transition_id": first["transition_id"]}]
        completion = first["to_screen_id"]
        if second_candidates:
            second = sorted(second_candidates, key=lambda item: item["transition_id"])[0]
            steps.append({"transition_id": second["transition_id"]})
            completion = second["to_screen_id"]
        identity = "|".join(step["transition_id"] for step in steps)
        flow_id = stable_id("flow", identity)
        if flow_id in flow_keys:
            continue
        flow_keys.add(flow_id)
        flows.append(
            {
                "flow_id": flow_id,
                "name": (
                    f"{screen_record_by_id[first['from_screen_id']]['name']} to "
                    f"{screen_record_by_id[completion]['name']}"
                ),
                "start_screen_id": first["from_screen_id"],
                "steps": steps,
                "completion_screen_id": completion,
                "preconditions": [],
                "confidence": confidence("statically_inferred", 0.65),
            }
        )

    # Runtime calibration is required for every source-only screen; one diagnostic per screen.
    element_counts = Counter(element["screen_id"] for element in elements)
    for screen in screens:
        add_diagnostic(
            diagnostics,
            diagnostic_seen,
            "requires_runtime_calibration",
            (
                "No explicitly identified development/test runtime was available. "
                "normalized_bounds remain null; physical coordinates, DPI, AutomationId "
                "matches, visibility, and actual navigation must be calibrated live."
            ),
            screen["source_evidence"],
            {"screen_id": screen["screen_id"]},
            0.5,
        )
        if element_counts[screen["screen_id"]] == 0:
            add_diagnostic(
                diagnostics,
                diagnostic_seen,
                "unconfirmed_element",
                "No reliable named/interactive/semantic child control was found statically.",
                screen["source_evidence"],
                {"screen_id": screen["screen_id"]},
                0.35,
            )
    for screen_id, targets in unresolved_by_screen.items():
        add_diagnostic(
            diagnostics,
            diagnostic_seen,
            "uncertain_transition",
            "Unresolved handler-created destinations: " + ", ".join(sorted(set(targets))),
            screen_record_by_id[screen_id]["source_evidence"],
            {"screen_id": screen_id},
            0.35,
        )

    # External/system/vendor windows are recorded without fabricating dangling screen IDs.
    external_patterns = re.compile(
        r"\b(MessageBox\.Show|OpenFileDialog|SaveFileDialog|FolderBrowserDialog|"
        r"SetShowWindow|ShowWindow)\b"
    )
    for path in ROOT.rglob("*.cs"):
        if is_skipped(path):
            continue
        text = read_text(path)
        matches = list(external_patterns.finditer(text))
        if not matches:
            continue
        details = sorted({match.group(1) for match in matches})
        first = matches[0]
        add_diagnostic(
            diagnostics,
            diagnostic_seen,
            "unconfirmed_screen",
            (
                "System/vendor/device UI reference requires an authorized test runtime: "
                + ", ".join(details)
            ),
            f"{rel(path)}:{line_number(text, first.start())}",
            None,
            0.4,
        )

    screens.sort(key=lambda item: item["screen_id"])
    elements.sort(key=lambda item: item["element_id"])
    transitions.sort(key=lambda item: item["transition_id"])
    flows.sort(key=lambda item: item["flow_id"])
    diagnostics.sort(key=lambda item: item["diagnostic_id"])

    # Preserve rich source-only inspection evidence outside the standard bundle.
    automation_gaps = []
    for record in source_records:
        if not record.get("automationId") and record.get("sourceName"):
            automation_gaps.append(
                {
                    "sourceFile": record["sourceFile"],
                    "sourceLine": record.get("sourceLine"),
                    "sourceName": record.get("sourceName"),
                    "reason": "Explicit AutomationId absent in source mapping.",
                }
            )
    inspection = {
        "schemaVersion": "1.0",
        "capture": {
            "capturedAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "repositoryRoot": str(ROOT),
            "processId": None,
            "executablePath": None,
            "architecture": None,
            "topLevelHwnd": None,
            "windowTitle": None,
            "locale": None,
            "monitor": None,
            "dpiX": None,
            "dpiY": None,
            "dpiScaleX": None,
            "dpiScaleY": None,
            "coordinateSpace": "source-only-no-runtime",
            "adapters": ["map-source-ui.ps1", "static-regex-and-source-analysis"],
        },
        "controls": [],
        "unmappedRuntimeControls": [],
        "sourceOnlyControls": source_records,
        "automationGaps": automation_gaps,
        "actions": [],
    }
    # Windows PowerShell 5's bundled validator relies on BOM auto-detection.
    # This rich evidence file is outside the standard bundle; bundle JSONL remains BOM-free.
    (EVIDENCE / "ui-inspection.json").write_bytes(
        (json.dumps(inspection, ensure_ascii=False, indent=2) + "\n").encode("utf-8-sig")
    )

    # Coverage report and machine-readable inventory include every candidate exactly once.
    inventory_rows = []
    for candidate in sorted(
        [item for item in candidates if not item.get("_component_instance")],
        key=lambda item: item["path"].lower(),
    ):
        status = candidate["disposition"]
        mapped = candidate.get("screen_id") or candidate.get("mapped_screen_id")
        inventory_rows.append(
            {
                "source_path": candidate["path"],
                "kind": candidate["kind"],
                "root_type": candidate["root_type"],
                "status": status,
                "mapped_screen_id": mapped,
                "mapped_screen_ids": candidate.get("mapped_screen_ids", [mapped] if mapped else []),
                "reason": candidate["reason"],
                "evidence": candidate["evidence"],
            }
        )
    (EVIDENCE / "ui-inventory.json").write_bytes(
        (json.dumps(inventory_rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    disposition_counts = Counter(row["status"] for row in inventory_rows)
    disposed = sum(disposition_counts.values())
    report_lines = [
        "# POS4U UI Analysis Coverage Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Inventory total: {len(inventory_rows)}",
        f"- Disposed: {disposed}",
        f"- Disposition rate: {(disposed / len(inventory_rows) * 100 if inventory_rows else 100):.2f}%",
        f"- Mapped as screens: {disposition_counts['screen'] + disposition_counts['dynamic_diagnostic']}",
        f"- Mapped as components/elements: {disposition_counts['component']}",
        f"- Resource/style/template: {disposition_counts['resource_template']}",
        f"- Explicitly excluded: {disposition_counts['excluded']}",
        f"- Dynamic/code-only requiring runtime: {disposition_counts['dynamic_diagnostic']}",
        f"- Bundle screens/elements/transitions/flows/diagnostics: {len(screens)}/{len(elements)}/{len(transitions)}/{len(flows)}/{len(diagnostics)}",
        f"- Statically analyzed screens: {sum(1 for item in screens if item['confidence']['level'] == 'statically_inferred')}",
        "- Runtime-confirmed screens: 0",
        "",
        "Runtime note: no explicitly identified development/test POS instance was available. "
        "No injection, payment, refund, void, settlement, device operation, or physical click was performed.",
        "",
        "## Complete coverage matrix",
        "",
        "| Source file | Kind/root | Disposition | Mapping | Evidence/reason |",
        "|---|---|---|---|---|",
    ]
    for row in inventory_rows:
        reason = (row["evidence"] + "; " + row["reason"]).replace("|", "\\|")
        report_lines.append(
            f"| `{row['source_path']}` | {row['kind']}/{row['root_type']} | "
            f"{row['status']} | `{row['mapped_screen_id'] or ''}` | {reason} |"
        )
    (OUTPUT / "coverage-report.md").write_bytes(
        ("\n".join(report_lines) + "\n").encode("utf-8")
    )

    # Start from the skill's blank template and replace only contract-defined files.
    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    shutil.copytree(TEMPLATE, BUNDLE)
    write_jsonl(BUNDLE / "screens.jsonl", screens)
    write_jsonl(BUNDLE / "elements.jsonl", elements)
    write_jsonl(BUNDLE / "transitions.jsonl", transitions)
    write_jsonl(BUNDLE / "flows.jsonl", flows)
    write_jsonl(BUNDLE / "diagnostics.jsonl", diagnostics)

    content = {}
    for name, required in (
        ("screens.jsonl", True),
        ("elements.jsonl", True),
        ("transitions.jsonl", True),
        ("flows.jsonl", False),
        ("diagnostics.jsonl", False),
    ):
        path = BUNDLE / name
        count = sum(1 for line in path.read_bytes().splitlines() if line.strip())
        content[name] = {
            "required": required,
            "sha256": sha256_file(path),
            "record_count": count,
        }
    revision = source_revision(candidates)
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest_lines = [
        'schema_version: "1.0"',
        'bundle_id: "pos4u-ui-analysis-v1"',
        'project_id: "pos4u-nodemaster"',
        f'generated_at: "{generated}"',
        "producer:",
        '  name: "pos4u-static-ui-index-builder"',
        '  version: "1.0.0"',
        f'source_revision: "{revision}"',
        'frameworks: ["wpf", "winforms", "razor", "html"]',
        'coordinate_spaces: ["normalized_1000"]',
        "default_viewports:",
        '  - name: "desktop"',
        "    width: 1920",
        "    height: 1080",
        "content_files:",
        "  manifest.yaml: {required: true, sha256: null, record_count: null}",
    ]
    for name in (
        "screens.jsonl",
        "elements.jsonl",
        "transitions.jsonl",
        "flows.jsonl",
        "diagnostics.jsonl",
    ):
        entry = content[name]
        required = "true" if entry["required"] else "false"
        manifest_lines.append(
            f'  {name}: {{required: {required}, sha256: "{entry["sha256"]}", '
            f'record_count: {entry["record_count"]}}}'
        )
    manifest_lines.extend(
        [
            "metadata:",
            '  analysis_mode: "full-static-source-analysis"',
            '  runtime_instance: "not-available-or-not-identified-as-test"',
            f"  inventory_total: {len(inventory_rows)}",
            f"  inventory_disposed: {disposed}",
            '  template: "generate-ui-analysis-index/assets/bundle-template/blank"',
        ]
    )
    (BUNDLE / "manifest.yaml").write_bytes(
        ("\n".join(manifest_lines) + "\n").encode("utf-8")
    )

    summary = {
        "bundle_dir": str(BUNDLE),
        "counts": {
            "screens": len(screens),
            "elements": len(elements),
            "transitions": len(transitions),
            "flows": len(flows),
            "diagnostics": len(diagnostics),
        },
        "inventory": {
            "total": len(inventory_rows),
            "disposed": disposed,
            "rate": 1.0 if len(inventory_rows) == disposed else 0.0,
            "by_status": dict(sorted(disposition_counts.items())),
        },
        "confidence": {
            "static_screens": sum(
                1
                for item in screens
                if item["confidence"]["level"] == "statically_inferred"
            ),
            "runtime_confirmed_screens": 0,
        },
        "content_files": content,
        "source_revision": revision,
    }
    (EVIDENCE / "generation-summary.json").write_bytes(
        (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
