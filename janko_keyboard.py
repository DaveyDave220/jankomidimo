import mido
from mido import Message
from pynput import keyboard
import tkinter as tk

BASE_NOTE = 60  # C4

# Keep the Janko geometry correct: each row advances in whole steps, and every
# 7th key horizontally is the same pitch class one octave higher.
#
# On a German keyboard the rows should look like this:
#   < y x c v b n m , . -     -> C D E F# G# A# C D E F# G# ...
#   a s d f g h j k l ö ä #   -> C# D# F G A A# C# D# F G A ...
#   q w e r t z u i o p ü +   -> C D E F# G# A# C D E F# G# ...
#
# This means the "7th horizontal" key is indeed the octave and the row offsets
# are semitone-shifted rather than going chromatically left-to-right.
key_map = {
    # Row 1: C, D, E, F#, G#, A#, C, D, E, F#, G#, A# ...
    '<': 0, 'y': 2, 'x': 4, 'c': 6, 'v': 8, 'b': 10, 'n': 12,
    'm': 14, ',': 16, '.': 18, '-': 20,

    # Row 2: C#, D#, F, G, A, A#, C#, D#, F, G, A, A# ...
    'a': 1, 's': 3, 'd': 5, 'f': 7, 'g': 9, 'h': 11, 'j': 13,
    'k': 15, 'l': 17, 'ö': 19, 'ä': 21, '#': 23,

    # Row 3: C, D, E, F#, G#, A#, C, D, E, F#, G#, A# ...
    'q': 0, 'w': 2, 'e': 4, 'r': 6, 't': 8, 'z': 10, 'u': 12,
    'i': 14, 'o': 16, 'p': 18, 'ü': 20, '+': 22,

    # German number row commonly used as the same Janko offset pattern.

    '1': -1, '2': 1, '3': 3, '4': 5, '5': 7, '6': 9, '7': 11,
    '8': 13, '9': 15, '0': 17, 'ß': 19, '´': 21,
}

# Actual physical keyboard layout: top row on top, bottom row on bottom, left-to-
# right in the normal reading order, with each lower row shifted slightly to the
# right so it visually resembles a real staggered keyboard.
PLACEHOLDER_KEY = '__left_pad__'

ROWS = [
    [PLACEHOLDER_KEY,'1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'ß', '´'],
    [PLACEHOLDER_KEY,'q', 'w', 'e', 'r', 't', 'z', 'u', 'i', 'o', 'p', 'ü', '+'],
    [PLACEHOLDER_KEY,'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'ö', 'ä', '#'],
    ['<', 'y', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '-'],
]

# Database of musical modes/chords as semitone offsets from the root note.
# Root is always assumed to be the bottom-left key of the mini template.
MODES = [
    {"name": "Major", "intervals": [0, 4, 7]},
    {"name": "Minor", "intervals": [0, 3, 7]},
    {"name": "Major7", "intervals": [0, 4, 7, 11]},
    {"name": "Minor7", "intervals": [0, 3, 7, 10]},
    {"name": "7", "intervals": [0, 4, 7, 10]},
    {"name": "dim7", "intervals": [0, 3, 6, 9]},
    {"name": "m6", "intervals": [0, 3, 7, 9]},
    {"name": "Sus2", "intervals": [0, 2, 7]},
    {"name": "Sus4", "intervals": [0, 5, 7]},
    {"name": "Dim", "intervals": [0, 3, 6]},
    {"name": "Aug", "intervals": [0, 4, 8]},
    {"name": "aug7", "intervals": [0, 4, 8, 10]},
]

# Two-column display order. Use None to leave an intentional empty slot.
MODE_GRID = [
    ["Major", "Minor", ],
    ["Major7", "Minor7"],
    ["7", "m6"],
    ["Aug", "Dim"],
    ["aug7", "dim7"],
    ["Sus2", "Sus4"],
]

ROW_OFFSETS = [0, 18, 36, 54]

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

pressed = set()
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

print("Verfügbare MIDI-Outputs:")
outputs = mido.get_output_names()
for i, name in enumerate(outputs):
    print(f"{i}: {name}")

if not outputs:
    print("Keine MIDI-Outputs gefunden. Starte z.B. eine DAW oder einen virtuellen Synth.")
    exit(1)


def select_midi_output(names):
    for i, name in enumerate(names):
        if "VirtualMIDISynth" in name:
            return i
    return 0


idx = select_midi_output(outputs)
print(f"Auto-selected MIDI output: {idx} -> {outputs[idx]}")
out = mido.open_output(outputs[idx])

print("\nSteuerung:")
print("  Z/X/C/... = Noten (Janko-Layout)")
print("  Pfeil hoch = Oktave hoch")
print("  Pfeil runter = Oktave runter")
print("  ESC = Beenden\n")


def note_name_for_midi(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{(midi // 12) - 1}"


def note_on(note: int, velocity_value: int | None = None):
    if muted:
        return

    current_velocity = volume if velocity_value is None else max(0, min(127, int(velocity_value)))
    if note in ringing_notes:
        out.send(Message('note_off', note=note, velocity=0))

    out.send(Message('note_on', note=note, velocity=current_velocity))
    ringing_notes.add(note)


def note_off(note: int):
    if note in ringing_notes:
        ringing_notes.remove(note)
    out.send(Message('note_off', note=note, velocity=0))


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
            semitone = key_map[key]
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
            semitone = key_map[key]
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
modes_canvas = None
modes_scrollbar = None
floating_window = None


def active_note_names():
    if not pressed:
        return "-"
    notes = []
    for key in sorted(pressed, key=lambda k: BASE_NOTE + key_map[k] + octave_shift + horizontal_shift):
        notes.append(note_name_for_midi(BASE_NOTE + key_map[key] + octave_shift + horizontal_shift))
    return ", ".join(notes)


def refresh_visuals():
    if root is None or status_var is None:
        return

    active = []
    for row in ROWS:
        for key in row:
            if key == PLACEHOLDER_KEY:
                continue

            container = key_boxes[key]
            note_label = note_labels[key]
            key_label = key_labels[key]

            midi = BASE_NOTE + key_map[key] + octave_shift + horizontal_shift
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

    status_var.set(f"Aktive Tasten: {', '.join(active) if active else '-'} | horizontal={horizontal_shift} | octave={octave_shift} | volume={volume}")
    if secondary_label is not None and secondary_window is not None and secondary_window.winfo_exists():
        secondary_label.config(text=f"Notes:\n{active_note_names()}\n\nHorizontal={horizontal_shift}\nOctave={octave_shift}\nVolume={volume}")
    root.update_idletasks()


def mode_preview_canvas(parent, mode_name, intervals):
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

    # Build the mode positions as semitone offsets from the root. Even
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

    preview.create_text(10, 60, anchor="nw", text=mode_name, fill="#f9fafb", font=("Segoe UI", 9, "bold"))
    return preview


def build_side_panel():
    global secondary_window, secondary_label, modes_canvas, modes_scrollbar

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
        text="Modes",
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

    modes_by_name = {mode["name"]: mode for mode in MODES}
    for mode_row in MODE_GRID:
        row = tk.Frame(inner, bg="#1f2937", pady=6)
        row.pack(fill="x", padx=8)
        for column, mode_name in enumerate(mode_row):
            cell = tk.Frame(row, bg="#1f2937", width=180, height=90)
            cell.grid(row=0, column=column, padx=2)
            cell.grid_propagate(False)
            if mode_name is not None:
                mode = modes_by_name[mode_name]
                mode_preview = mode_preview_canvas(cell, mode["name"], mode["intervals"])
                mode_preview.pack(side="left", padx=8)

    inner.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))
    canvas.bind("<Configure>", lambda event: canvas.config(scrollregion=canvas.bbox("all")))
    canvas.pack(side="left", fill="both", expand=True, padx=8, pady=(0, 8))
    scrollbar.pack(side="right", fill="y", pady=(0, 8))

    secondary_label = header
    modes_canvas = canvas
    modes_scrollbar = scrollbar


def build_floating_panel():
    global secondary_window, secondary_label

    if getattr(root, "side_panel", None) is not None:
        root.side_panel.destroy()
        root.side_panel = None

    if secondary_window is not None and secondary_window.winfo_exists():
        secondary_window.destroy()

    secondary_window = tk.Toplevel(root)
    secondary_window.title("Janko extra")
    secondary_window.geometry("220x250")
    secondary_window.configure(bg="#111827")

    label = tk.Label(
        secondary_window,
        text=f"Notes:\n{active_note_names()}\n\nHorizontal={horizontal_shift}\nOctave={octave_shift}",
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


def build_visual_window():
    global root, status_var, key_boxes, note_labels, key_labels, volume_var, volume_label_var, mute_button, sustain_indicator

    root = tk.Tk()
    root.title("Davidaves Musikbox a la Janko")
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
    volume_panel.pack(fill="x", padx=16, pady=(0, 16))
    volume_panel.pack_propagate(False)

    volume_var = tk.IntVar(value=volume)
    volume_label_var = tk.StringVar(value=f"Volume: {volume}")

    mute_button = tk.Button(
        volume_panel,
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
        volume_panel,
        textvariable=volume_label_var,
        bg="#1f2937",
        fg="#f9fafb",
        font=("Segoe UI", 10, "bold"),
        anchor="w",
        padx=8,
    )
    volume_label.pack(side="left", fill="y", pady=10)

    volume_slider = tk.Scale(
        volume_panel,
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

    if panel_mode == "side":
        build_side_panel()

    for row_index, row in enumerate(ROWS):
        row_frame = tk.Frame(frame, bg="#111827")
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

            note = note_name_for_midi(BASE_NOTE + key_map[key] + octave_shift)
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

    root.update_idletasks()
    refresh_visuals()


def on_press(key):
    global octave_shift, horizontal_shift, sustain_pedal

    try:
        k = key.char.lower()
    except AttributeError:
        k = None

    if isinstance(key, keyboard.Key):
        if key == keyboard.Key.esc:
            print("Beende...")
            return False
        elif key == keyboard.Key.up:
            octave_shift += 12
            print(f"Oktave hoch: shift = {octave_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.down:
            octave_shift -= 12
            print(f"Oktave runter: shift = {octave_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.left:
            horizontal_shift -= 1
            print(f"Horizontal links: shift = {horizontal_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.right:
            horizontal_shift += 1
            print(f"Horizontal rechts: shift = {horizontal_shift}")
            refresh_visuals()
            return
        elif key == keyboard.Key.space:
            sustain_pedal = True
            if sustain_indicator is not None:
                sustain_indicator.config(text="Sustain: on", fg="#ffdd57")
            print("Sustain pedal: on")
            return

    if k and k in key_map and k not in pressed:
        pressed.add(k)
        print(f"pressed now: {sorted(pressed)}")
        semitone = key_map[k]
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

    if isinstance(key, keyboard.Key) and key == keyboard.Key.space:
        sustain_pedal = False
        if sustain_indicator is not None:
            sustain_indicator.config(text="Sustain: off", fg="#f9fafb")
        print("Sustain pedal: off")
        release_all_active_notes()
        return

    if k and k in pressed:
        pressed.remove(k)
        semitone = key_map[k]
        note = BASE_NOTE + semitone + octave_shift + horizontal_shift
        if not sustain_pedal:
            note_off(note)
        if root is not None:
            root.after(0, refresh_visuals)


if __name__ == "__main__":
    build_visual_window()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    root.mainloop()
    listener.stop()
