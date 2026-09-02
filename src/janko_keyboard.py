from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
import tomllib

import mido
from mido import Message
from pynput import keyboard
import tkinter as tk

from settings import (
    BASE_NOTE,
    CHORD_GRID,
    CHORDS,
    NOTE_NAMES,
    PLACEHOLDER_KEY,
    ROW_OFFSETS,
    ROWS,
    DEFAULT_LAYOUT,
    KEYBOARD_LAYOUTS,
    key_map,
)


def get_project_version():
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        with pyproject_path.open("rb") as pyproject_file:
            return tomllib.load(pyproject_file)["project"]["version"]
    except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
        try:
            return package_version("janko-keyboard")
        except PackageNotFoundError:
            return "unknown"


VERSION = get_project_version()

pressed = set()
held_navigation_keys = set()
ringing_notes = set()
octave_shift = 0
horizontal_shift = 0
volume = 90
muted = False
sustain_pedal = False
volume_var = None
volume_label_var = None
mute_button = None
sustain_indicator = None
midi_output_var = None
midi_output_menu = None
keyboard_layout_var = None
keyboard_layout_menu = None
NO_MIDI_OUTPUT = "No MIDI output"
current_layout_name = DEFAULT_LAYOUT
current_key_map = key_map
current_rows = ROWS

print("Available MIDI outputs:")
outputs = mido.get_output_names()
for i, name in enumerate(outputs):
    print(f"{i}: {name}")

if not outputs:
    print("No MIDI outputs found. Start a DAW or virtual synth, for example.")
    exit(1)


def select_midi_output(names):
    for i, name in enumerate(names):
        if "VirtualMIDISynth" in name:
            return i
    return 0


idx = select_midi_output(outputs)
print(f"Auto-selected MIDI output: {idx} -> {outputs[idx]}")
out = mido.open_output(outputs[idx])

print("\nControls:")
print("  Z/X/C/... = Notes (Janko layout)")
print("  Up arrow = Octave up")
print("  Down arrow = Octave down")
print("  Left/Right arrows = Horizontal shift")
print("  Space = Sustain (hold)")
print("  ESC = Exit\n")


def note_name_for_midi(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{(midi // 12) - 1}"


def note_on(note: int, velocity_value: int | None = None):
    if muted or out is None:
        return

    current_velocity = volume if velocity_value is None else max(0, min(127, int(velocity_value)))
    if note in ringing_notes:
        out.send(Message('note_off', note=note, velocity=0))

    out.send(Message('note_on', note=note, velocity=current_velocity))
    ringing_notes.add(note)


def note_off(note: int):
    if note in ringing_notes:
        ringing_notes.remove(note)
    if out is not None:
        out.send(Message('note_off', note=note, velocity=0))


def switch_midi_output(output_name):
    global out

    current_output_name = out.name if out is not None else NO_MIDI_OUTPUT
    if output_name == current_output_name:
        return

    if output_name == NO_MIDI_OUTPUT:
        release_all_active_notes()
        out.close()
        out = None
        print("MIDI output disabled")
        return

    try:
        next_output = mido.open_output(output_name)
    except OSError as error:
        print(f"Could not open MIDI output {output_name}: {error}")
        if midi_output_var is not None:
            midi_output_var.set(current_output_name)
        return

    if out is not None:
        release_all_active_notes()
        out.close()
    out = next_output
    print(f"MIDI output changed to: {output_name}")


def switch_keyboard_layout(layout_name):
    global current_layout_name, current_key_map, current_rows

    if layout_name not in KEYBOARD_LAYOUTS or layout_name == current_layout_name:
        return

    release_all_active_notes()
    layout = KEYBOARD_LAYOUTS[layout_name]
    current_layout_name = layout_name
    current_key_map = layout["key_map"]
    current_rows = layout["rows"]
    print(f"Keyboard layout changed to: {layout_name}")

    if root is not None:
        rebuild_keyboard()


def set_volume(new_value):
    global volume

    try:
        next_volume = max(0, min(127, int(new_value)))
    except (TypeError, ValueError):
        return

    if next_volume == volume:
        return

    volume = next_volume

    if volume_var is not None and volume_var.get() != volume:
        volume_var.set(volume)
    if volume_label_var is not None:
        volume_label_var.set(f"Volume: {volume}")

    if pressed:
        active_notes = list(pressed)
        for key in active_notes:
            semitone = current_key_map[key]
            note = BASE_NOTE + semitone + octave_shift + horizontal_shift
            note_off(note)
            note_on(note)

    if root is not None:
        refresh_visuals()


def toggle_mute():
    global muted

    muted = not muted
    if mute_button is not None:
        mute_button.config(text="Mute" if muted else "Unmute")
        mute_button.configure(bg="#f59e0b" if muted else "#1f2937")

    if pressed:
        active_notes = list(pressed)
        for key in active_notes:
            semitone = current_key_map[key]
            note = BASE_NOTE + semitone + octave_shift + horizontal_shift
            note_off(note)
            if not muted:
                note_on(note)

    if volume_label_var is not None:
        volume_label_var.set(f"Volume: {volume} (muted)" if muted else f"Volume: {volume}")

    if root is not None:
        refresh_visuals()


def release_all_active_notes():
    for note in list(ringing_notes):
        note_off(note)
    pressed.clear()
    if root is not None:
        root.after(0, refresh_visuals)


root = None
key_boxes = {}
note_labels = {}
key_labels = {}
status_var = None
panel_mode = "side"  # "side" or "floating"
secondary_window = None
secondary_label = None
chords_canvas = None
chords_scrollbar = None
floating_window = None


def active_note_names():
    if not pressed:
        return "-"
    notes = []
    for key in sorted(pressed, key=lambda k: BASE_NOTE + current_key_map[k] + octave_shift + horizontal_shift):
        notes.append(note_name_for_midi(BASE_NOTE + current_key_map[key] + octave_shift + horizontal_shift))
    return ", ".join(notes)


def refresh_visuals():
    if root is None or status_var is None:
        return

    active = []
    for row in current_rows:
        for key in row:
            if key == PLACEHOLDER_KEY:
                continue

            container = key_boxes[key]
            note_label = note_labels[key]
            key_label = key_labels[key]

            midi = BASE_NOTE + current_key_map[key] + octave_shift + horizontal_shift
            note = note_name_for_midi(midi)
            is_natural = midi % 12 in {0, 2, 4, 5, 7, 9, 11}

            if key in pressed:
                active.append(note_name_for_midi(midi))
                container.config(bg="#ffdd57", highlightbackground="#ffb703", highlightthickness=2, relief="solid")
                note_label.config(bg="#ffdd57", fg="#1c1c1c")
                key_label.config(bg="#ffdd57", fg="#1c1c1c")
            else:
                if is_natural:
                    container.config(bg="#f5f7fa", highlightbackground="#d1d5db", highlightthickness=2, relief="flat")
                    note_label.config(bg="#f5f7fa", fg="#1c1c1c")
                    key_label.config(bg="#f5f7fa", fg="#1c1c1c")
                else:
                    container.config(bg="#2d3748", highlightbackground="#4b5563", highlightthickness=2, relief="flat")
                    note_label.config(bg="#2d3748", fg="#f5f7fa")
                    key_label.config(bg="#2d3748", fg="#f5f7fa")

            note_label.config(text=note)
            key_label.config(text=key.upper() if len(key) == 1 else key)

    status_var.set(f"Active Buttons: {', '.join(active) if active else '-'} | horizontal={horizontal_shift} | octave={octave_shift} | volume={volume}")
    if secondary_label is not None and secondary_window is not None and secondary_window.winfo_exists():
            secondary_label.config(text=f"WORK IN PROGRESS\n\nNotes:\n{active_note_names()}\n\nHorizontal={horizontal_shift}\nOctave={octave_shift}\nVolume={volume}")
    root.update_idletasks()


def chord_preview_canvas(parent, chord_name, intervals):
    preview = tk.Canvas(parent, width=160, height=80, bg="#111827", highlightthickness=0)

    min_x, min_y = 10, 10
    cell_w, cell_h = 18, 18
    dot_r = 4

    # Draw a small 2-row mini key grid; root is assumed at the bottom-left.
    # The preview is a reduced Janko-like layout, without note names.
    for row_index in range(2):
        for col in range(6):
            row_offset = cell_w / 2 if row_index == 0 else 0
            x0 = min_x + row_offset + col * cell_w
            y0 = min_y + row_index * cell_h
            preview.create_rectangle(x0, y0, x0 + cell_w - 4, y0 + cell_h - 4, outline="#374151", fill="#1f2937")

    # Build the chord positions as semitone offsets from the root. Even
    # semitones are on the bottom row; odd semitones are on the staggered top row.
    root_positions = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    for offset in intervals:
        if offset not in root_positions:
            continue
        col = offset // 2
        row = 1 if offset % 2 == 0 else 0
        row_offset = cell_w / 2 if row == 0 else 0
        x = min_x + row_offset + col * cell_w + cell_w / 2 - 2
        y = min_y + row * cell_h + cell_h / 2
        preview.create_oval(x - dot_r, y - dot_r, x + dot_r, y + dot_r, fill="#ffdd57", outline="#ffb703")

    preview.create_text(10, 60, anchor="nw", text=chord_name, fill="#f9fafb", font=("Segoe UI", 9, "bold"))
    return preview


def build_side_panel():
    global secondary_window, secondary_label, chords_canvas, chords_scrollbar

    if secondary_window is not None and secondary_window.winfo_exists():
        secondary_window.destroy()
        secondary_window = None

    if getattr(root, "side_panel", None) is not None:
        root.side_panel.destroy()
        root.side_panel = None

    side_panel = tk.Frame(root.content_frame, bg="#1f2937", width=420)
    side_panel.pack(side="right", fill="y", padx=12, pady=16)
    side_panel.pack_propagate(False)
    root.side_panel = side_panel

    header = tk.Label(
        side_panel,
        text="Chords",
        bg="#1f2937",
        fg="#f9fafb",
        font=("Segoe UI", 12, "bold"),
        anchor="w",
        padx=12,
        pady=8,
    )
    header.pack(fill="x")

    canvas = tk.Canvas(side_panel, bg="#1f2937", highlightthickness=0, width=380, height=420)
    scrollbar = tk.Scrollbar(side_panel, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    inner = tk.Frame(canvas, bg="#1f2937")
    canvas.create_window((0, 0), window=inner, anchor="nw")

    chords_by_name = {chord["name"]: chord for chord in CHORDS}
    for chord_row in CHORD_GRID:
        row = tk.Frame(inner, bg="#1f2937", pady=6)
        row.pack(fill="x", padx=8)
        for column, chord_name in enumerate(chord_row):
            cell = tk.Frame(row, bg="#1f2937", width=180, height=90)
            cell.grid(row=0, column=column, padx=2)
            cell.grid_propagate(False)
            if chord_name is not None:
                chord = chords_by_name[chord_name]
                chord_preview = chord_preview_canvas(cell, chord["name"], chord["intervals"])
                chord_preview.pack(side="left", padx=8)

    inner.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))
    canvas.bind("<Configure>", lambda event: canvas.config(scrollregion=canvas.bbox("all")))
    canvas.pack(side="left", fill="both", expand=True, padx=8, pady=(0, 8))
    scrollbar.pack(side="right", fill="y", pady=(0, 8))

    secondary_label = header
    chords_canvas = canvas
    chords_scrollbar = scrollbar


def build_floating_panel():
    global secondary_window, secondary_label

    if getattr(root, "side_panel", None) is not None:
        root.side_panel.destroy()
        root.side_panel = None

    if secondary_window is not None and secondary_window.winfo_exists():
        secondary_window.destroy()

    secondary_window = tk.Toplevel(root)
    secondary_window.title("Janko extra - Work in progress")
    secondary_window.geometry("220x250")
    secondary_window.configure(bg="#111827")

    label = tk.Label(
        secondary_window,
        text=f"WORK IN PROGRESS\n\nNotes:\n{active_note_names()}\n\nHorizontal={horizontal_shift}\nOctave={octave_shift}",
        bg="#111827",
        fg="#f9fafb",
        justify="left",
        anchor="nw",
        font=("Segoe UI", 11, "bold"),
        padx=12,
        pady=12,
    )
    label.pack(fill="both", expand=True)
    secondary_label = label


def toggle_panel_mode():
    global panel_mode

    if panel_mode == "side":
        panel_mode = "floating"
        build_floating_panel()
    else:
        panel_mode = "side"
        build_side_panel()


def rebuild_keyboard():
    if root is None or not hasattr(root, "keyboard_frame"):
        return

    for child in root.keyboard_frame.winfo_children():
        child.destroy()
    key_boxes.clear()
    note_labels.clear()
    key_labels.clear()

    for row_index, row in enumerate(current_rows):
        row_frame = tk.Frame(root.keyboard_frame, bg="#111827")
        row_frame.pack(fill="x", pady=8)

        for key in row:
            if key == PLACEHOLDER_KEY:
                btn = tk.Button(
                    row_frame,
                    text="",
                    width=8,
                    height=2,
                    bg="#1f2937",
                    fg="#f5f7fa",
                    highlightthickness=1,
                    highlightbackground="#374151",
                    relief="flat",
                    justify="center",
                )
                btn.pack(side="left", padx=4, pady=2)
                key_boxes[key] = btn
                continue

            note = note_name_for_midi(BASE_NOTE + current_key_map[key] + octave_shift)
            slot = tk.Frame(
                row_frame,
                width=86,
                height=72,
                bg="#2d3748",
                highlightthickness=2,
                highlightbackground="#4b5563",
                relief="flat",
            )
            slot.pack_propagate(False)
            slot.pack(side="left", padx=4, pady=2)

            note_label = tk.Label(
                slot,
                text=note,
                bg="#2d3748",
                fg="#f5f7fa",
                font=("Segoe UI", 14, "bold"),
                justify="center",
                anchor="center",
            )
            note_label.place(relx=0.5, rely=0.38, anchor="center")

            key_label = tk.Label(
                slot,
                text=key.upper() if len(key) == 1 else key,
                bg="#2d3748",
                fg="#c0c0c0",
                font=("Segoe UI", 8),
                justify="left",
                anchor="w",
            )
            key_label.place(x=6, y=62, anchor="sw")

            key_boxes[key] = slot
            note_labels[key] = note_label
            key_labels[key] = key_label

        row_frame.pack(anchor="n", padx=ROW_OFFSETS[row_index])

    refresh_visuals()


def build_visual_window():
    global root, status_var, volume_var, volume_label_var, mute_button, sustain_indicator, midi_output_var, midi_output_menu, keyboard_layout_var, keyboard_layout_menu

    root = tk.Tk()
    root.title(f"jankomidimo {VERSION}")
    root.geometry("1400x600")
    root.configure(bg="#111827")

    root.option_add("*Background", "#111827")
    root.option_add("*Foreground", "#f5f7fa")
    root.option_add("*Button.Background", "#2d3748")
    root.option_add("*Button.Foreground", "#f5f7fa")
    root.option_add("*Label.Background", "#111827")
    root.option_add("*Label.Foreground", "#f9fafb")
    root.option_add("*Frame.Background", "#111827")

    status_var = tk.StringVar(value="Aktive Tasten: -")
    label = tk.Label(root, textvariable=status_var, bg="#111827", fg="#f9fafb", font=("Segoe UI", 12, "bold"))
    label.pack(anchor="w", padx=16, pady=8)

    toggle_btn = tk.Button(
        root,
        text="Toggle panel",
        command=toggle_panel_mode,
        bg="#1f2937",
        fg="#f5f7fa",
        highlightthickness=1,
        highlightbackground="#374151",
        relief="flat",
    )
    toggle_btn.pack(anchor="e", padx=16, pady=8)

    root.content_frame = tk.Frame(root, bg="#111827")
    root.content_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    frame = tk.Frame(root.content_frame, bg="#111827")
    frame.pack(side="left", fill="both", expand=True)

    sustain_indicator = tk.Label(
        root,
        text="Sustain: off",
        bg="#111827",
        fg="#f9fafb",
        font=("Segoe UI", 9, "bold"),
        anchor="w",
    )
    sustain_indicator.pack(anchor="w", padx=16, pady=(0, 4))

    volume_panel = tk.Frame(root, bg="#1f2937", height=68, highlightthickness=1, highlightbackground="#374151")
    volume_panel.pack(fill="x", padx=16, pady=(0, 8))
    volume_panel.pack_propagate(False)

    volume_var = tk.IntVar(value=volume)
    volume_label_var = tk.StringVar(value=f"Volume: {volume}")

    volume_controls = tk.Frame(volume_panel, bg="#1f2937")
    volume_controls.pack(side="left", fill="both", expand=True)

    mute_button = tk.Button(
        volume_controls,
        text="Mute",
        command=toggle_mute,
        width=8,
        bg="#1f2937",
        fg="#f5f7fa",
        highlightthickness=1,
        highlightbackground="#374151",
        relief="flat",
    )
    mute_button.pack(side="left", padx=(12, 8), pady=10)

    volume_label = tk.Label(
        volume_controls,
        textvariable=volume_label_var,
        bg="#1f2937",
        fg="#f9fafb",
        font=("Segoe UI", 10, "bold"),
        anchor="w",
        padx=8,
    )
    volume_label.pack(side="left", fill="y", pady=10)

    volume_slider = tk.Scale(
        volume_controls,
        from_=0,
        to=127,
        orient=tk.HORIZONTAL,
        variable=volume_var,
        command=set_volume,
        length=420,
        showvalue=False,
        bg="#1f2937",
        fg="#f5f7fa",
        highlightthickness=0,
        troughcolor="#374151",
        activebackground="#ffdd57",
    )
    volume_slider.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)

    midi_controls = tk.Frame(volume_panel, bg="#1f2937")
    midi_controls.pack(side="left", fill="both", expand=True)

    midi_label = tk.Label(
        midi_controls,
        text="MIDI output:",
        bg="#1f2937",
        fg="#f9fafb",
        font=("Segoe UI", 10, "bold"),
    )
    midi_label.pack(side="left", padx=(12, 8), pady=8)

    midi_output_var = tk.StringVar(value=out.name)
    midi_output_menu = tk.OptionMenu(
        midi_controls,
        midi_output_var,
        *outputs,
        NO_MIDI_OUTPUT,
        command=switch_midi_output,
    )
    midi_output_menu.config(
        bg="#2d3748",
        fg="#f5f7fa",
        activebackground="#4b5563",
        activeforeground="#f5f7fa",
        highlightthickness=0,
        relief="flat",
    )
    midi_output_menu.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=8)

    layout_controls = tk.Frame(volume_panel, bg="#1f2937")
    layout_controls.pack(side="left", fill="both", expand=True)

    layout_label = tk.Label(
        layout_controls,
        text="Keyboard layout:",
        bg="#1f2937",
        fg="#f9fafb",
        font=("Segoe UI", 10, "bold"),
    )
    layout_label.pack(side="left", padx=(12, 8), pady=8)

    keyboard_layout_var = tk.StringVar(value=current_layout_name)
    keyboard_layout_menu = tk.OptionMenu(
        layout_controls,
        keyboard_layout_var,
        *KEYBOARD_LAYOUTS,
        command=switch_keyboard_layout,
    )
    keyboard_layout_menu.config(
        bg="#2d3748",
        fg="#f5f7fa",
        activebackground="#4b5563",
        activeforeground="#f5f7fa",
        highlightthickness=0,
        relief="flat",
    )
    keyboard_layout_menu.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=8)

    controls_legend = tk.Frame(root, bg="#1f2937", highlightthickness=1, highlightbackground="#374151")
    controls_legend.pack(fill="x", padx=16, pady=(0, 8))

    controls_label = tk.Label(
        controls_legend,
        text=(
            "Controls:  A/S/D/... Play notes  |  Arrow Up/Down: Change Octave  |  "
            "Arrow Left/Right: Shift Notes  |  Space: Sustain (hold)  |  ESC: Exit"
        ),
        bg="#1f2937",
        fg="#f9fafb",
        font=("Segoe UI", 9),
        anchor="w",
        padx=12,
        pady=8,
    )
    controls_label.pack(fill="x")

    if panel_mode == "side":
        build_side_panel()

    root.keyboard_frame = frame
    rebuild_keyboard()

    root.update_idletasks()


def on_press(key):
    global octave_shift, horizontal_shift, sustain_pedal

    try:
        k = key.char.lower()
    except AttributeError:
        k = None

    if isinstance(key, keyboard.Key):
        if key == keyboard.Key.esc:
            print("Exiting...")
            if root is not None:
                root.after(0, root.destroy)
            return False
        elif key == keyboard.Key.up:
            if key in held_navigation_keys:
                return
            held_navigation_keys.add(key)
            octave_shift += 12
            print(f"Octave up: shift = {octave_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.down:
            if key in held_navigation_keys:
                return
            held_navigation_keys.add(key)
            octave_shift -= 12
            print(f"Octave down: shift = {octave_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.left:
            if key in held_navigation_keys:
                return
            held_navigation_keys.add(key)
            horizontal_shift -= 1
            print(f"Horizontal left: shift = {horizontal_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.right:
            if key in held_navigation_keys:
                return
            held_navigation_keys.add(key)
            horizontal_shift += 1
            print(f"Horizontal right: shift = {horizontal_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.space:
            sustain_pedal = True
            if sustain_indicator is not None:
                sustain_indicator.config(text="Sustain: on", fg="#ffdd57")
            print("Sustain pedal: on")
            return

    if k and k in current_key_map and k not in pressed:
        pressed.add(k)
        print(f"Pressed keys: {sorted(pressed)}")
        semitone = current_key_map[k]
        note = BASE_NOTE + semitone + octave_shift + horizontal_shift
        if note in ringing_notes:
            note_off(note)
        note_on(note)
        if root is not None:
            root.after(0, refresh_visuals)


def on_release(key):
    global sustain_pedal

    try:
        k = key.char.lower()
    except AttributeError:
        k = None

    if isinstance(key, keyboard.Key) and key in held_navigation_keys:
        held_navigation_keys.remove(key)
        return

    if isinstance(key, keyboard.Key) and key == keyboard.Key.space:
        sustain_pedal = False
        if sustain_indicator is not None:
            sustain_indicator.config(text="Sustain: off", fg="#f9fafb")
        print("Sustain pedal: off")
        release_all_active_notes()
        return

    if k and k in pressed:
        pressed.remove(k)
        semitone = current_key_map[k]
        note = BASE_NOTE + semitone + octave_shift + horizontal_shift
        if not sustain_pedal:
            note_off(note)
        if root is not None:
            root.after(0, refresh_visuals)


def main():
    build_visual_window()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    root.mainloop()
    listener.stop()


if __name__ == "__main__":
    main()
