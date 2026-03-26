# gui.py
import customtkinter as ctk
from tkinter import filedialog
from dotenv import dotenv_values


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AIBooru Auto-Poster")
        self.geometry("900x500")
        self.minsize(700, 400)

        ctk.set_appearance_mode("dark")

        self._build_layout()
        self._prefill_from_env()

    def _build_layout(self):
        # Main container: left panel + right panel
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === Left panel ===
        left = ctk.CTkFrame(self, width=250)
        left.grid(row=0, column=0, sticky="ns", padx=(10, 5), pady=10)
        left.grid_propagate(False)

        # Folder
        ctk.CTkLabel(left, text="Папка с изображениями").pack(padx=10, pady=(10, 2), anchor="w")
        folder_frame = ctk.CTkFrame(left, fg_color="transparent")
        folder_frame.pack(padx=10, fill="x")

        self.folder_entry = ctk.CTkEntry(folder_frame, state="readonly")
        self.folder_entry.pack(side="left", fill="x", expand=True)

        self.browse_btn = ctk.CTkButton(folder_frame, text="Обзор", width=70, command=self._browse_folder)
        self.browse_btn.pack(side="right", padx=(5, 0))

        # Limit
        ctk.CTkLabel(left, text="Лимит постов (пусто = все)").pack(padx=10, pady=(15, 2), anchor="w")
        self.limit_entry = ctk.CTkEntry(left, placeholder_text="все")
        self.limit_entry.pack(padx=10, fill="x")

        # Stop on error checkbox
        self.stop_on_error_var = ctk.BooleanVar(value=False)
        self.stop_on_error_cb = ctk.CTkCheckBox(
            left, text="Останавливаться\nпри ошибках", variable=self.stop_on_error_var
        )
        self.stop_on_error_cb.pack(padx=10, pady=(15, 5), anchor="w")

        # Buttons
        self.start_btn = ctk.CTkButton(
            left, text="\u25b6  Запустить", fg_color="#2fa572", hover_color="#1f7a53",
            command=self._on_start,
        )
        self.start_btn.pack(padx=10, pady=(15, 5), fill="x")

        self.stop_btn = ctk.CTkButton(
            left, text="\u23f9  Стоп", state="disabled",
            command=self._on_stop,
        )
        self.stop_btn.pack(padx=10, fill="x")

        # Progress
        self.progress_label = ctk.CTkLabel(left, text="0 / 0")
        self.progress_label.pack(padx=10, pady=(15, 2))

        self.progress_bar = ctk.CTkProgressBar(left)
        self.progress_bar.pack(padx=10, fill="x")
        self.progress_bar.set(0)

        # === Right panel (log) ===
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 13), state="disabled")
        self.log_box.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        # Configure text tags for colored log output
        self.log_box.tag_config("error", foreground="#ff4444")
        self.log_box.tag_config("warning", foreground="#ffaa00")

    def _prefill_from_env(self):
        try:
            values = dotenv_values(".env")
            images_dir = values.get("IMAGES_DIR", "")
            if images_dir:
                self.folder_entry.configure(state="normal")
                self.folder_entry.insert(0, images_dir)
                self.folder_entry.configure(state="readonly")
        except Exception:
            pass

    def _browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_entry.configure(state="normal")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, path)
            self.folder_entry.configure(state="readonly")

    def _on_start(self):
        pass  # Task 6

    def _on_stop(self):
        pass  # Task 6

    def _log(self, message: str, level: str = "info"):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        # Trim to 5000 lines
        line_count = int(self.log_box.index("end-1c").split(".")[0])
        if line_count > 5000:
            self.log_box.delete("1.0", f"{line_count - 5000}.0")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")


if __name__ == "__main__":
    app = App()
    app.mainloop()
