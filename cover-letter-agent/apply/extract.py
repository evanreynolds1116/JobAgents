"""Read a form's fields from the page (spec: How it works, step 3): label, kind, options,
required flag and current value. Works from the page structure, not screenshots.

Each field's control (or each option of a radio or checkbox group) gets a data-ja-key
attribute so the filler can find it again. Searchable dropdowns (Greenhouse's comboboxes)
only show their options when opened, so each one is opened, read and closed.
"""

from dataclasses import asdict, dataclass, field

from apply import guard

KINDS = ("text", "email", "tel", "url", "number", "date", "textarea", "select", "combobox", "radio",
         "checkbox_group", "checkbox", "buttons", "file")  # buttons: a Yes/No toggle-button question


@dataclass
class Field:
    key: str
    kind: str
    label: str
    required: bool = False
    options: list[str] = field(default_factory=list)
    value: str | list[str] = ""
    multiple: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


READ_FIELDS = r"""
() => {
  const visible = el => !!(el.offsetParent || el.getClientRects().length) &&
                        getComputedStyle(el).visibility !== 'hidden';
  const clean = t => (t || '').replace(/[*✱]/g, ' ').replace(/\s+/g, ' ').trim();
  const generic = t => /^((attach|upload|browse|choose( a)? file|select( a)? file|drop files?( here)?|enter manually|dropbox|google drive|select\.*)\s*)*$/i.test(clean(t));
  const groupOf = el => el.closest('[role="group"][aria-labelledby], [role="radiogroup"][aria-labelledby]');
  const textOf = id => { const n = document.getElementById(id); return n ? n.innerText : ''; };

  // The question text around a control or group: the first piece of text in the nearest
  // ancestor that isn't an option label, a dropdown's options or a generic word like Attach.
  const questionFor = (el, optionTexts) => {
    const fs = el.closest('fieldset');
    if (fs) { const lg = fs.querySelector('legend'); if (lg && clean(lg.innerText)) return clean(lg.innerText); }
    const skip = new Set(optionTexts.map(clean));
    let node = el.parentElement;
    for (let depth = 0; node && depth < 7; depth++, node = node.parentElement) {
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const parent = walker.currentNode.parentElement;
        if (!parent || parent.closest('select, option, script, style, [role="listbox"], [role="option"]')) continue;
        const line = clean(walker.currentNode.textContent);
        if (line.length > 1 && !generic(line) && !skip.has(line)) return line;
      }
    }
    return '';
  };
  const labelFor = el => {
    let t = '';
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) t = l.innerText; }
    if (!clean(t) || generic(t)) { const l = el.closest('label'); if (l) t = l.innerText; }
    if (!clean(t) || generic(t)) t = el.getAttribute('aria-labelledby')
        ? el.getAttribute('aria-labelledby').split(/\s+/).map(textOf).join(' ') : t;
    if (!clean(t) || generic(t)) t = el.getAttribute('aria-label') || t;
    if (!clean(t) || generic(t)) { const g = groupOf(el); if (g) t = g.getAttribute('aria-labelledby').split(/\s+/).map(textOf).join(' '); }
    if (!clean(t) || generic(t)) t = questionFor(el, el.tagName === 'SELECT' ? [...el.options].map(o => o.text) : []);
    if (!clean(t)) t = el.getAttribute('placeholder') || el.name || el.id || '';
    return clean(t);
  };
  const labelElement = el => (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) ||
                             (el.name && document.querySelector(`label[for="${CSS.escape(el.name)}"]`)) || null;
  const isRequired = (el, rawLabel) => el.required || el.getAttribute('aria-required') === 'true' ||
                                       groupOf(el)?.getAttribute('aria-required') === 'true' ||
                                       /required/i.test(labelElement(el)?.className || '') ||
                                       /[*✱]/.test(rawLabel || '');

  const fields = [];
  const elementOf = {};
  const groups = new Map();
  let n = 0;

  // Toggle-button questions (Ashby's Yes/No): two or more buttons with aria-pressed, often
  // with a hidden checkbox behind them.
  const toggles = [];
  for (const box of document.querySelectorAll('div, fieldset, span')) {
    const buttons = [...box.children].filter(c => c.tagName === 'BUTTON' && c.hasAttribute('aria-pressed'));
    if (buttons.length < 2 || !visible(box) || box.closest('[data-ja-ignore]')) continue;
    toggles.push(box);
    const key = 'f' + (n++);
    buttons.forEach((b, i) => { b.setAttribute('data-ja-key', key); b.setAttribute('data-ja-option', i); });
    const options = buttons.map(b => clean(b.innerText));
    const hidden = box.querySelector('input');
    const lab = hidden ? labelElement(hidden) : null;
    const label = clean(lab?.innerText) || questionFor(box, options);
    elementOf[key] = box;
    fields.push({key, kind: 'buttons', label, options, multiple: false,
                 required: /required/i.test(lab?.className || '') || /[*✱]/.test(lab?.innerText || ''),
                 value: options[buttons.findIndex(b => b.getAttribute('aria-pressed') === 'true')] || ''});
  }

  const controls = document.querySelectorAll('input, select, textarea');
  for (const el of controls) {
    if (toggles.some(t => t.contains(el))) continue;
    const type = (el.getAttribute('type') || el.type || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes(type)) continue;
    if (el.getAttribute('aria-hidden') === 'true' || el.disabled) continue;
    if (type !== 'file' && !visible(el)) continue;
    if (el.closest('[data-ja-ignore]')) continue;

    if (type === 'radio' || type === 'checkbox') {
      const name = el.name || el.id;
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(el);
      continue;
    }
    const key = 'f' + (n++);
    el.setAttribute('data-ja-key', key);
    const rawLabel = (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.innerText) || '';
    const label = labelFor(el);
    let kind = type || el.tagName.toLowerCase();
    if (el.tagName === 'SELECT') kind = 'select';
    else if (el.tagName === 'TEXTAREA') kind = 'textarea';
    else if (el.getAttribute('role') === 'combobox') kind = 'combobox';
    else if (!['email', 'tel', 'url', 'number', 'date', 'file'].includes(kind)) kind = 'text';
    let value = el.value || '';
    let options = [];
    let multiple = false;
    if (kind === 'select') {
      options = [...el.options].filter(o => o.value !== '' && !/^(select|choose|please select|--)/i.test(o.text.trim()))
                               .map(o => clean(o.text));
      multiple = el.multiple;
      value = el.multiple ? [...el.selectedOptions].map(o => clean(o.text))
                          : (el.value ? clean(el.selectedOptions[0]?.text || '') : '');
    } else if (kind === 'combobox') {
      const box = el.closest('[class*="control"]') || el.parentElement?.parentElement || el;
      const chosen = [...box.querySelectorAll('[class*="single-value"], [class*="multi-value__label"]')]
                     .map(c => clean(c.innerText));
      multiple = !!box.querySelector('[class*="multi-value"]') || /mark all|select all|check all/i.test(label);
      value = multiple ? chosen : (chosen[0] || '');
    } else if (kind === 'file') {
      value = el.files && el.files.length ? el.files[0].name : '';
    }
    elementOf[key] = el;
    fields.push({key, kind, label, required: isRequired(el, rawLabel || label), options, value, multiple});
  }
  for (const [name, inputs] of groups) {
    const key = 'f' + (n++);
    const optionLabels = inputs.map(i => labelFor(i));
    inputs.forEach((i, idx) => { i.setAttribute('data-ja-key', key); i.setAttribute('data-ja-option', idx); });
    elementOf[key] = inputs[0];
    const single = inputs.length === 1 && inputs[0].type === 'checkbox';
    const label = single ? optionLabels[0] : questionFor(inputs[0], optionLabels);
    fields.push({
      key, kind: single ? 'checkbox' : (inputs[0].type === 'radio' ? 'radio' : 'checkbox_group'),
      label: clean(label), required: inputs.some(i => i.required || i.getAttribute('aria-required') === 'true'),
      options: single ? [] : optionLabels,
      value: single ? (inputs[0].checked ? 'checked' : '') :
             (inputs[0].type === 'radio' ? (optionLabels[inputs.findIndex(i => i.checked)] || '')
                                         : optionLabels.filter((_, i) => inputs[i].checked)),
      multiple: inputs[0].type === 'checkbox' && !single,
    });
  }
  // Page order, so the review table reads like the form.
  return fields.sort((a, b) =>
    elementOf[a.key].compareDocumentPosition(elementOf[b.key]) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);
}
"""

READ_OPTIONS = r"""
() => [...document.querySelectorAll('[role="option"]')].filter(o => o.offsetParent || o.getClientRects().length)
        .map(o => o.innerText.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 80)
"""


def read_fields(page, open_dropdowns: bool = True) -> list[Field]:
    """Every fillable field on the page, in page order for single controls, then groups."""
    fields = [Field(**raw) for raw in page.evaluate(READ_FIELDS)]
    if open_dropdowns:
        for f in fields:
            if f.kind == "combobox" and not f.options:
                f.options = combobox_options(page, f.key)
    return fields


def combobox_options(page, key: str) -> list[str]:
    """Open a searchable dropdown, read its options and close it again."""
    box = page.locator(f'[data-ja-key="{key}"]')
    try:
        guard.safe_click(box)
        page.wait_for_timeout(300)
        options = page.evaluate(READ_OPTIONS)
    except guard.SubmitBlocked:
        return []
    except Exception:  # noqa: BLE001 - a dropdown that won't open just has no listed options
        options = []
    finally:
        try:
            box.press("Escape")
        except Exception:  # noqa: BLE001
            pass
    return options


def current_values(page) -> dict[str, str | list[str]]:
    """The value of every field now, keyed by label, for saving what was finally entered,
    including your edits (spec: How it works, step 8)."""
    return {f.label: f.value for f in read_fields(page, open_dropdowns=False)}
