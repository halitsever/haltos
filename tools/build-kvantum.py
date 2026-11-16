#!/usr/bin/env python3
"""Generates the HaltMono Kvantum theme (kvconfig + SVG) from shadcn zinc dark tokens."""
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "kvantum", "HaltMono")

T = {
    "bg": "#09090b",
    "card": "#09090b",
    "muted": "#18181b",
    "accent": "#27272a",
    "border": "#27272a",
    "strong": "#3f3f46",
    "hover": "#52525b",
    "subtle": "#71717a",
    "muted_fg": "#a1a1aa",
    "ring": "#d4d4d8",
    "fg": "#fafafa",
    "primary": "#fafafa",
    "primary_fg": "#18181b",
}

STATES = ("normal", "focused", "pressed", "toggled", "disabled")


class Svg:
    def __init__(self):
        self.parts = []
        self.y = 0

    def slot(self, h):
        """Each element gets its own row so bounding boxes never overlap."""
        y = self.y
        self.y += h + 8
        return y

    def group(self, eid, x, y, w, h, body=""):
        self.parts.append(
            f'<g id="{eid}"><rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="#000" fill-opacity="0"/>{body}</g>'
        )

    def render(self):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="{self.y}" viewBox="0 0 400 {self.y}">'
            + "".join(self.parts)
            + "</svg>\n"
        )


def corner_paths(x, y, s, b, sx, sy):
    """Border ring and fill for one rounded corner. sx/sy mirror the top-left corner into the others."""

    def p(px, py):
        return (x + (px if sx > 0 else s - px), y + (py if sy > 0 else s - py))

    sweep_o = 1 if sx * sy > 0 else 0
    sweep_i = 1 - sweep_o
    a, c = p(0, s), p(s, 0)
    d, e = p(s, b), p(b, s)
    ring = f"M{a[0]:g},{a[1]:g} A{s:g},{s:g} 0 0 {sweep_o} {c[0]:g},{c[1]:g} L{d[0]:g},{d[1]:g} A{s - b:g},{s - b:g} 0 0 {sweep_i} {e[0]:g},{e[1]:g} Z"
    ctr = p(s, s)
    fill = f"M{ctr[0]:g},{ctr[1]:g} L{e[0]:g},{e[1]:g} A{s - b:g},{s - b:g} 0 0 {sweep_o} {d[0]:g},{d[1]:g} Z"
    return ring, fill


def frame(svg, name, state, s, fill=None, border=None, b=1):
    """Emits the 8 frame pieces and the interior for one element state. None means transparent."""
    y = svg.slot(s * 3)
    fl = f'fill="{fill}"' if fill else 'fill="none"'
    bd = f'fill="{border}"' if border else 'fill="none"'
    pre = f"{name}-{state}" if state else name

    for part, (cx, sx, sy) in {
        "topleft": (0, 1, 1),
        "topright": (2 * s, -1, 1),
        "bottomleft": (0, 1, -1),
        "bottomright": (2 * s, -1, -1),
    }.items():
        cy = y if sy > 0 else y + 2 * s
        ring, f = corner_paths(cx, cy, s, b, sx, sy)
        svg.group(f"{pre}-{part}", cx, cy, s, s, f'<path d="{f}" {fl}/><path d="{ring}" {bd}/>')

    edges = {
        "top": (s, y, s, s, (s, y, s, b), (s, y + b, s, s - b)),
        "bottom": (s, y + 2 * s, s, s, (s, y + 3 * s - b, s, b), (s, y + 2 * s, s, s - b)),
        "left": (0, y + s, s, s, (0, y + s, b, s), (b, y + s, s - b, s)),
        "right": (2 * s, y + s, s, s, (3 * s - b, y + s, b, s), (2 * s, y + s, s - b, s)),
    }
    for part, (x0, y0, w, h, br, fr) in edges.items():
        body = f'<rect x="{fr[0]:g}" y="{fr[1]:g}" width="{fr[2]:g}" height="{fr[3]:g}" {fl}/>'
        body += f'<rect x="{br[0]:g}" y="{br[1]:g}" width="{br[2]:g}" height="{br[3]:g}" {bd}/>'
        svg.group(f"{pre}-{part}", x0, y0, w, h, body)
    svg.group(pre, s, y + s, s, s, f'<rect x="{s:g}" y="{y + s:g}" width="{s:g}" height="{s:g}" {fl}/>')


def element(svg, name, s, styles):
    for state in STATES:
        fill, border = styles.get(state, styles["normal"])
        frame(svg, name, state, s, fill, border)


def icon(svg, eid, body_fn, size=16):
    y = svg.slot(size)
    svg.group(eid, 0, y, size, size, body_fn(0, y, size))


def chevron(direction, color, width=1.6):
    pts = {
        "down": [(4.5, 6.5), (8, 10), (11.5, 6.5)],
        "up": [(4.5, 9.5), (8, 6), (11.5, 9.5)],
        "right": [(6.5, 4.5), (10, 8), (6.5, 11.5)],
        "left": [(9.5, 4.5), (6, 8), (9.5, 11.5)],
    }[direction]

    def f(x, y, s):
        k = s / 16
        d = "M" + " L".join(f"{x + px * k:g},{y + py * k:g}" for px, py in pts)
        return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'

    return f


def plus_minus(kind, color):
    def f(x, y, s):
        d = f"M{x + 4:g},{y + 8:g} L{x + 12:g},{y + 8:g}"
        if kind == "plus":
            d += f" M{x + 8:g},{y + 4:g} L{x + 8:g},{y + 12:g}"
        return f'<path d="{d}" stroke="{color}" stroke-width="1.6" stroke-linecap="round"/>'

    return f


def checkbox(kind, state):
    on = kind != "off"
    border = {"disabled": T["border"], "focused": T["muted_fg"]}.get(state, T["subtle"])
    fill = "none"
    if on:
        border = fill = T["strong"] if state == "disabled" else T["primary"]

    def f(x, y, s):
        out = f'<rect x="{x + 1.5:g}" y="{y + 1.5:g}" width="13" height="13" rx="3.5" fill="{fill}" stroke="{border}" stroke-width="1"/>'
        if kind == "on":
            out += f'<path d="M{x + 4.5:g},{y + 8.2:g} L{x + 7:g},{y + 10.6:g} L{x + 11.6:g},{y + 5.6:g}" fill="none" stroke="{T["primary_fg"]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
        elif kind == "tri":
            out += f'<path d="M{x + 5:g},{y + 8:g} L{x + 11:g},{y + 8:g}" stroke="{T["primary_fg"]}" stroke-width="1.8" stroke-linecap="round"/>'
        return out

    return f


def radio(on, state):
    border = {"disabled": T["border"], "focused": T["muted_fg"]}.get(state, T["subtle"])
    if on:
        border = T["strong"] if state == "disabled" else T["primary"]

    def f(x, y, s):
        out = f'<circle cx="{x + 8:g}" cy="{y + 8:g}" r="6.5" fill="none" stroke="{border}" stroke-width="1"/>'
        if on:
            out += f'<circle cx="{x + 8:g}" cy="{y + 8:g}" r="3.5" fill="{border}"/>'
        return out

    return f


def build_svg():
    svg = Svg()
    R, Rs = 6, 4
    b, acc, strong, p = T["border"], T["accent"], T["strong"], T["primary"]

    # Outline button; pressed and checked flip to the primary (white) look.
    element(svg, "button", R, {
        "normal": (T["bg"], b), "focused": (acc, b), "pressed": (strong, strong),
        "toggled": (p, p), "disabled": (T["bg"], T["muted"]),
    })
    # Ghost button for toolbars.
    element(svg, "tbutton", R, {
        "normal": (None, None), "focused": (acc, None), "pressed": (strong, None),
        "toggled": (acc, b), "disabled": (None, None),
    })
    element(svg, "menubaritem", Rs, {
        "normal": (None, None), "focused": (acc, None), "pressed": (acc, None), "toggled": (acc, None),
    })
    element(svg, "lineedit", R, {
        "normal": (None, b), "focused": (None, T["ring"]), "pressed": (None, T["ring"]),
        "toggled": (None, T["ring"]), "disabled": (None, T["muted"]),
    })
    element(svg, "common", 8, {"normal": (None, b), "disabled": (None, T["muted"])})
    element(svg, "group", 8, {"normal": (None, b)})
    element(svg, "itemview", Rs, {
        "normal": (None, None), "focused": (T["muted"], None), "pressed": (acc, None), "toggled": (acc, None),
    })
    element(svg, "menu", 8, {"normal": (T["bg"], b)})
    element(svg, "menuitem", Rs, {
        "normal": (None, None), "focused": (acc, None), "pressed": (acc, None), "toggled": (acc, None),
    })
    element(svg, "tooltip", R, {"normal": (p, p)})
    element(svg, "tab", R, {
        "normal": (None, None), "focused": (T["muted"], None), "pressed": (acc, None),
        "toggled": (acc, b), "disabled": (None, None),
    })
    element(svg, "header", 2, {"normal": (T["bg"], None), "focused": (T["muted"], None), "pressed": (acc, None), "toggled": (T["muted"], None)})
    element(svg, "scrollbargroove", 4, {"normal": (None, None)})
    element(svg, "scrollbarslider", 4, {
        "normal": (strong, None), "focused": (T["hover"], None), "pressed": (T["subtle"], None),
        "toggled": (T["hover"], None), "disabled": (T["accent"], None),
    })
    element(svg, "ss", 3, {"normal": (strong, None), "focused": (T["hover"], None), "pressed": (T["subtle"], None)})
    element(svg, "slider", 2, {"normal": (acc, None), "toggled": (p, None), "disabled": (T["muted"], None)})
    element(svg, "progress", 3, {"normal": (acc, None)})
    element(svg, "progress-pattern", 3, {"normal": (p, None), "disabled": (strong, None)})
    element(svg, "splitter", 1, {"normal": (None, None), "focused": (strong, None), "pressed": (T["subtle"], None)})
    element(svg, "toolbar", 2, {"normal": (None, None)})
    element(svg, "titlebar", 2, {"normal": (T["bg"], None)})

    for state in STATES:
        color = {"normal": T["muted_fg"], "disabled": T["strong"], "toggled": T["primary_fg"]}.get(state, T["fg"])
        for d in ("up", "down", "left", "right"):
            icon(svg, f"arrow-{d}-{state}", chevron(d, color))
        icon(svg, f"arrow-plus-{state}", plus_minus("plus", color))
        icon(svg, f"arrow-minus-{state}", plus_minus("minus", color))
        icon(svg, f"tree-plus-{state}", chevron("right", color))
        icon(svg, f"tree-minus-{state}", chevron("down", color))
        icon(svg, f"tab-close-{state}", lambda x, y, s, c=color: f'<path d="M{x + 5:g},{y + 5:g} L{x + 11:g},{y + 11:g} M{x + 11:g},{y + 5:g} L{x + 5:g},{y + 11:g}" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>')
        icon(svg, f"checkbox-{state}", checkbox("off", state))
        icon(svg, f"checkbox-checked-{state}", checkbox("on", state))
        icon(svg, f"checkbox-tristate-{state}", checkbox("tri", state))
        icon(svg, f"radio-{state}", radio(False, state))
        icon(svg, f"radio-checked-{state}", radio(True, state))
        for m, d in {
            "close": "M5,5 L11,11 M11,5 L5,11",
            "minimize": "M4.5,10.5 L11.5,10.5",
            "maximize": "M4.5,4.5 h7 v7 h-7 Z",
            "restore": "M6.5,4.5 h5 v5 M4.5,6.5 h5 v5 h-5 Z",
            "menu": "M4.5,6 h7 M4.5,10 h7",
            "shade": "M4.5,9.5 L8,6 L11.5,9.5",
            "unshade": "M4.5,6.5 L8,10 L11.5,6.5",
        }.items():
            icon(svg, f"mdi-{m}-{state}", lambda x, y, s, d=d, c=color: f'<path transform="translate({x:g},{y:g})" d="{d}" fill="none" stroke="{c}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>')

    def dot_grid(x, y, s):
        return "".join(
            f'<circle cx="{x + s / 2 + dx:g}" cy="{y + s / 2 + dy:g}" r="1" fill="{T["subtle"]}"/>'
            for dx in (-3, 0, 3) for dy in (-3, 0, 3) if dx + dy >= 0
        )

    for state in STATES:
        icon(svg, f"slidercursor-{state}", lambda x, y, s, st=state: f'<circle cx="{x + 8:g}" cy="{y + 8:g}" r="6.5" fill="{T["bg"]}" stroke="{T["strong"] if st == "disabled" else p}" stroke-width="2"/>')
        icon(svg, f"resize-grip-{state}", dot_grid)
        icon(svg, f"splitter-grip-{state}", lambda x, y, s: "")
        icon(svg, f"grip-{state}", lambda x, y, s: "")
    # Keyboard focus shows as a soft ring instead of Qt's dashed rectangle.
    frame(svg, "focus", None, R, None, T["subtle"])
    icon(svg, "button-default-indicator", lambda x, y, s: "")
    icon(svg, "dial", lambda x, y, s: f'<circle cx="{x + 8:g}" cy="{y + 8:g}" r="7.5" fill="{T["muted"]}" stroke="{T["strong"]}" stroke-width="1"/>')
    icon(svg, "dial-handle", lambda x, y, s: f'<circle cx="{x + 8:g}" cy="{y + 8:g}" r="4" fill="{p}"/>')
    icon(svg, "dial-notches", lambda x, y, s: "")
    icon(svg, "toolbar-handle", lambda x, y, s: "".join(f'<circle cx="{x + 8:g}" cy="{y + 4 + i * 4:g}" r="1" fill="{T["strong"]}"/>' for i in range(3)))
    icon(svg, "toolbar-separator", lambda x, y, s: f'<rect x="{x + 7.5:g}" y="{y + 2:g}" width="1" height="12" fill="{T["border"]}"/>')
    icon(svg, "menu-separator", lambda x, y, s: f'<rect x="{x:g}" y="{y + 7.5:g}" width="{s:g}" height="1" fill="{T["border"]}"/>')
    return svg.render()


def build_kvconfig():
    fg, mfg, pfg = T["fg"], T["muted_fg"], T["primary_fg"]
    sections = {
        "%General": {
            "author": "HaltOS", "comment": "shadcn-style monochrome theme for HaltOS",
            "x11drag": "menubar_and_primary_toolbar", "alt_mnemonic": "true", "left_tabs": "false",
            "attach_active_tab": "false", "center_normal_tabs": "false", "group_toolbar_buttons": "false",
            "spread_progressbar": "true", "progressbar_thickness": "6", "composite": "true",
            "translucent_windows": "false", "menu_shadow_depth": "0", "tooltip_shadow_depth": "0",
            "spread_menuitems": "true", "menu_separator_height": "9", "splitter_width": "5",
            "scroll_width": "10", "scroll_min_extent": "40", "scroll_arrows": "false",
            "transient_scrollbar": "true", "transient_groove": "false", "combo_as_lineedit": "true",
            "combo_menu": "true", "hide_combo_checkboxes": "true", "inline_spin_indicators": "true",
            "slider_width": "4", "slider_handle_width": "16", "slider_handle_length": "16",
            "check_size": "16", "button_icon_size": "16", "toolbar_icon_size": "16",
            "small_icon_size": "16", "large_icon_size": "32", "layout_spacing": "6", "layout_margin": "10",
            "submenu_overlap": "0", "dark_titlebar": "true", "animate_states": "true",
            "no_inactiveness": "true", "respect_DE": "true", "popup_blurring": "false",
            "menu_blur_radius": "0", "tooltip_blur_radius": "0", "click_behavior": "1",
        },
        "GeneralColors": {
            "window.color": T["bg"], "base.color": T["bg"], "alt.base.color": "#111113",
            "button.color": T["muted"], "light.color": T["strong"], "mid.light.color": T["accent"],
            "dark.color": "#000000", "mid.color": T["accent"], "highlight.color": T["accent"],
            "inactive.highlight.color": T["muted"], "text.color": fg, "window.text.color": fg,
            "button.text.color": fg, "disabled.text.color": T["subtle"], "tooltip.text.color": pfg,
            "highlight.text.color": fg, "link.color": T["ring"], "link.visited.color": mfg,
            "progress.indicator.text.color": pfg,
        },
        "Hacks": {
            "respect_darkness": "true", "transparent_ktitle_label": "true", "transparent_dolphin_view": "false",
            "lxqtmainmenu_iconsize": "16", "blur_translucent": "false", "no_selection_tint": "true",
            "tint_on_mouseover": "0", "centered_forms": "false", "middle_click_scroll": "false",
        },
        "PanelButtonCommand": {
            "frame": "true", "frame.element": "button", "frame.top": "6", "frame.bottom": "6",
            "frame.left": "6", "frame.right": "6", "interior": "true", "interior.element": "button",
            "indicator.size": "12", "indicator.element": "arrow", "text.normal.color": fg,
            "text.focus.color": fg, "text.press.color": fg, "text.toggle.color": pfg,
            "text.disabled.color": T["subtle"], "text.shadow": "0", "text.margin": "1",
            "text.margin.top": "2", "text.margin.bottom": "2", "text.margin.left": "6",
            "text.margin.right": "6", "text.iconspacing": "6", "min_height": "+6",
        },
        "PanelButtonTool": {"inherits": "PanelButtonCommand", "frame.element": "tbutton", "interior.element": "tbutton", "text.toggle.color": fg},
        "ToolboxTab": {"inherits": "PanelButtonTool"},
        "Dock": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false"},
        "DockTitle": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false", "text.bold": "true"},
        "IndicatorSpinBox": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false", "indicator.element": "arrow", "indicator.size": "12"},
        "RadioButton": {"inherits": "PanelButtonCommand", "frame": "false", "interior.element": "radio", "text.toggle.color": fg},
        "CheckBox": {"inherits": "PanelButtonCommand", "frame": "false", "interior.element": "checkbox", "text.toggle.color": fg},
        "GenericFrame": {"inherits": "PanelButtonCommand", "frame": "true", "interior": "false", "frame.element": "common", "interior.element": "common", "frame.top": "8", "frame.bottom": "8", "frame.left": "8", "frame.right": "8"},
        "LineEdit": {"inherits": "PanelButtonCommand", "frame.element": "lineedit", "interior.element": "lineedit", "text.margin.left": "4", "text.margin.right": "4"},
        "ComboBox": {"inherits": "PanelButtonCommand", "text.toggle.color": fg},
        "DropDownButton": {"inherits": "PanelButtonCommand", "indicator.element": "arrow-down"},
        "IndicatorArrow": {"indicator.element": "arrow", "indicator.size": "12"},
        "Tab": {"inherits": "PanelButtonCommand", "frame.element": "tab", "interior.element": "tab", "indicator.element": "tab", "text.normal.color": mfg, "text.focus.color": fg, "text.press.color": fg, "text.toggle.color": fg, "text.margin.left": "10", "text.margin.right": "10", "text.margin.top": "4", "text.margin.bottom": "4", "min_height": "+4"},
        "TabFrame": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false"},
        "TabBarFrame": {"inherits": "GenericFrame", "frame": "false", "interior": "false"},
        "TreeExpander": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false", "indicator.element": "tree", "indicator.size": "12"},
        "HeaderSection": {"inherits": "PanelButtonCommand", "frame.element": "header", "interior.element": "header", "frame.top": "2", "frame.bottom": "2", "frame.left": "2", "frame.right": "2", "text.normal.color": mfg, "text.toggle.color": fg, "text.bold": "false"},
        "SizeGrip": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false", "indicator.element": "resize-grip", "indicator.size": "13"},
        "Toolbar": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false", "indicator.element": "toolbar", "indicator.size": "6", "text.margin": "0"},
        "Slider": {"inherits": "PanelButtonCommand", "frame.element": "slider", "interior.element": "slider", "frame.top": "2", "frame.bottom": "2", "frame.left": "2", "frame.right": "2"},
        "SliderCursor": {"inherits": "PanelButtonCommand", "frame": "false", "interior.element": "slidercursor"},
        "Progressbar": {"inherits": "PanelButtonCommand", "frame.element": "progress", "interior.element": "progress", "frame.top": "3", "frame.bottom": "3", "frame.left": "3", "frame.right": "3", "text.margin": "0", "text.normal.color": fg, "text.bold": "false"},
        "ProgressbarContents": {"inherits": "PanelButtonCommand", "frame.element": "progress-pattern", "interior.element": "progress-pattern", "frame.top": "3", "frame.bottom": "3", "frame.left": "3", "frame.right": "3"},
        "ItemView": {"inherits": "PanelButtonCommand", "frame.element": "itemview", "interior.element": "itemview", "frame.top": "4", "frame.bottom": "4", "frame.left": "4", "frame.right": "4", "text.margin": "1", "text.margin.top": "2", "text.margin.bottom": "2", "text.margin.left": "4", "text.margin.right": "4", "text.toggle.color": fg, "min_height": "+4"},
        "Splitter": {"inherits": "PanelButtonCommand", "frame": "false", "interior.element": "splitter", "indicator.element": "splitter-grip", "indicator.size": "16"},
        "Scrollbar": {"inherits": "PanelButtonCommand", "indicator.size": "0"},
        "ScrollbarSlider": {"inherits": "PanelButtonCommand", "frame.element": "scrollbarslider", "interior.element": "scrollbarslider", "frame.top": "4", "frame.bottom": "4", "frame.left": "4", "frame.right": "4", "indicator.element": "grip", "indicator.size": "0"},
        "ScrollbarTransientSlider": {"frame": "true", "frame.element": "ss", "interior": "false", "frame.top": "3", "frame.bottom": "3", "frame.left": "3", "frame.right": "3"},
        "ScrollbarGroove": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false"},
        "Menu": {"inherits": "PanelButtonCommand", "frame.element": "menu", "interior.element": "menu", "frame.top": "8", "frame.bottom": "8", "frame.left": "8", "frame.right": "8", "text.toggle.color": fg},
        "MenuItem": {"inherits": "PanelButtonCommand", "frame.element": "menuitem", "interior.element": "menuitem", "indicator.element": "arrow", "frame.top": "4", "frame.bottom": "4", "frame.left": "4", "frame.right": "4", "text.margin.top": "2", "text.margin.bottom": "2", "text.margin.left": "6", "text.margin.right": "6", "text.toggle.color": fg, "min_height": "+6"},
        "MenuBar": {"inherits": "PanelButtonCommand", "frame": "false", "interior": "false"},
        "MenuBarItem": {"inherits": "PanelButtonCommand", "frame.element": "menubaritem", "interior.element": "menubaritem", "frame.top": "4", "frame.bottom": "4", "frame.left": "4", "frame.right": "4", "text.margin.left": "8", "text.margin.right": "8", "text.toggle.color": fg},
        "TitleBar": {"inherits": "PanelButtonCommand", "frame": "false", "interior.element": "titlebar", "indicator.element": "mdi", "indicator.size": "16", "text.normal.color": mfg, "text.focus.color": fg, "text.bold": "true"},
        "GroupBox": {"inherits": "GenericFrame", "frame.element": "group", "text.margin": "0", "text.normal.color": fg, "text.bold": "true"},
        "ToolTip": {"inherits": "GenericFrame", "frame.element": "tooltip", "interior": "true", "interior.element": "tooltip", "frame.top": "6", "frame.bottom": "6", "frame.left": "6", "frame.right": "6", "text.margin": "2", "text.normal.color": pfg},
        "StatusBar": {"inherits": "GenericFrame", "frame": "false", "interior": "false"},
        "Window": {"interior": "false", "frame": "false"},
        "Focus": {"frame": "false", "frame.element": "focus"},
    }
    lines = []
    for sec, kv in sections.items():
        lines.append(f"[{sec}]")
        lines += [f"{k}={v}" for k, v in kv.items()]
        lines.append("")
    return "\n".join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "HaltMono.kvconfig"), "w") as f:
        f.write(build_kvconfig())
    with open(os.path.join(OUT, "HaltMono.svg"), "w") as f:
        f.write(build_svg())
    print(OUT)


if __name__ == "__main__":
    main()
