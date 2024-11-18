import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import logging
import traceback
import os
import queue
from ftc_scraper.service import get_driver, first_page, base_url, quote, BeautifulSoup, per_page_operation

name = 'FTC Scraper'


class Logger(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.textbox = tk.Text(self, width=90, height=30, state="disabled", wrap="word")
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.textbox.yview)
        self.textbox.config(yscrollcommand=self.scrollbar.set)
        self.textbox.tag_config("info")
        self.textbox.tag_config("error", foreground="red")
        self.textbox.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.scrollbar.pack(side="right", fill="y")

    def log_text(self, text: str, tag: str) -> None:
        self.textbox.config(state="normal")
        self.textbox.insert("end", f"{text}\n", tag)
        self.textbox.config(state="disabled")
        self.textbox.see(tk.END)

    def info(self, text: str) -> None:
        self.log_text(text, "info")

    def error(self, text: str) -> None:
        self.log_text(text, "error")


class TextHandler(logging.Handler):
    def __init__(self, logger_widget):
        super().__init__()
        self.logger_widget = logger_widget

    def emit(self, record):
        msg = self.format(record)
        tag = "info" if record.levelno < logging.ERROR else "error"
        self.logger_widget.log_text(msg, tag)


class PDFGeneratorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(name)
        self.root.geometry("800x600")
        self.root.resizable(False, False)

        # Main frame
        self.main_frame = tk.Frame(root, padx=20, pady=20)
        self.main_frame.pack(fill="both", expand=True)

        # Title
        self.title_label = tk.Label(self.main_frame, text=name, font=("Arial", 20, "bold"))
        self.title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # String input section
        self.string_label = tk.Label(self.main_frame, text="Enter Text:")
        self.string_label.grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.string_entry = tk.Entry(self.main_frame, width=50)
        self.string_entry.grid(row=1, column=1, columnspan=2, pady=(0, 10), sticky="ew")

        # Destination folder selection
        self.folder_label = tk.Label(self.main_frame, text="Select Destination Folder:")
        self.folder_label.grid(row=2, column=0, sticky="w", pady=(0, 10))
        self.folder_frame = tk.Frame(self.main_frame)
        self.folder_frame.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(0, 10))
        self.folder_entry = tk.Entry(self.folder_frame, width=40)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        self.folder_button = tk.Button(self.folder_frame, text="Browse", command=self.browse_folder)
        self.folder_button.pack(side="right", padx=(5, 0))

        # Submit button
        self.submit_button = tk.Button(self.main_frame, text="Generate PDFs", command=self.generate_pdfs)
        self.submit_button.grid(row=3, column=0, columnspan=3, pady=(20, 10))

        # Progress bar
        self.progress = ttk.Progressbar(self.main_frame, orient='horizontal', mode='determinate', length=400)
        self.progress.grid(row=4, column=0, columnspan=3, pady=(10, 5))

        # Progress label
        self.progress_label = tk.Label(self.main_frame, text="")
        self.progress_label.grid(row=5, column=0, columnspan=3)

        # Logging area
        self.logger_frame = Logger(self.main_frame)
        self.logger_frame.grid(row=6, column=0, columnspan=3, pady=(20, 0), sticky="nsew")
        self.main_frame.rowconfigure(6, weight=1)

        # Logger configuration
        self.logger = logging.getLogger('PDFGenerator')
        self.logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler('logs.log')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        ui_handler = TextHandler(self.logger_frame)
        ui_handler.setLevel(logging.DEBUG)
        ui_handler.setFormatter(formatter)
        self.logger.addHandler(ui_handler)

        self.queue = queue.Queue()
        self.root.after(100, self.process_queue)

    def browse_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_path)

    def generate_pdfs(self):
        text = self.string_entry.get()
        dest_folder = self.folder_entry.get()

        if not text or not dest_folder:
            messagebox.showerror("Error", "Please enter text and select a destination folder")
            return

        if not os.path.exists(dest_folder):
            messagebox.showerror("Error", "The selected folder does not exist")
            return

        threading.Thread(target=self.generate_pdfs_thread, args=(text, dest_folder)).start()

    def generate_pdfs_thread(self, text, dest_folder):
        try:
            self.queue.put(('submit_button', 'disabled'))
            self.queue.put(('progress', 0))
            self.queue.put(('progress_label', "0%"))
            with get_driver() as driver:
                self.logger.info("Fething the number of pages ...")
                page_nos = first_page(self.logger, text, dest_folder, driver)
                self.logger.info(f"Total pages found: {page_nos}")
                for i in range(2, page_nos+1):
                    url = base_url.format(query=quote(text), page=i)
                    self.logger.info(f"Processing page {i} of {page_nos} - {url}")
                    driver.get(url)
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    per_page_operation(self.logger, soup, dest_folder)
                    progress_percentage = (i + 1) / page_nos * 100
                    self.queue.put(('progress', progress_percentage))
                    self.queue.put(('progress_label', f"{progress_percentage:.2f}% ({i + 1}/{page_nos})"))

            self.logger.info("Completed.")
            # # Simulate generating PDFs
            # total_pdfs = 5  # Example: generating 5 PDFs
            # for i in range(total_pdfs):
            #     pdf_path = generate_pdf_from_string(text, dest_folder, f"output_{i + 1}.pdf")
            #     self.logger.info(f"Generated PDF: {pdf_path}")

            #     progress_percentage = (i + 1) / total_pdfs * 100
            #     self.queue.put(('progress', progress_percentage))
            #     self.queue.put(('progress_label', f"{progress_percentage:.2f}% ({i + 1}/{total_pdfs})"))

            self.logger.info("PDF Saved.")
            self.queue.put(('messagebox', ('info', "PDF generation completed successfully.")))
        except Exception as e:
            self.logger.error("Error occurred: %s", str(e))
            self.logger.error(traceback.format_exc())
            self.queue.put(('messagebox', ('error', str(e))))
        finally:
            self.queue.put(('submit_button', 'normal'))
            self.queue.put(('progress', 100))
            self.queue.put(('progress_label', "100%"))

    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            if msg[0] == 'submit_button':
                self.submit_button.config(state=msg[1])
            elif msg[0] == 'progress':
                self.progress['value'] = msg[1]
            elif msg[0] == 'progress_label':
                self.progress_label.config(text=msg[1])
            elif msg[0] == 'messagebox':
                if msg[1][0] == 'info':
                    messagebox.showinfo("Info", msg[1][1])
                elif msg[1][0] == 'error':
                    messagebox.showerror("Error", msg[1][1])
        self.root.after(100, self.process_queue)
    
    def main(self, log, query, save_path, queue):
        with get_driver() as driver:
            page_nos = first_page(log, query, save_path, driver)
            log.info(f"Total pages found: {page_nos}")
            for i in range(2, page_nos+1):
                url = base_url.format(query=quote(query), page=i)
                log.info(f"Processing page {i} of {page_nos} - {url}")
                driver.get(url)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                per_page_operation(log, soup, save_path)
        log.info("Completed.")


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFGeneratorApp(root)
    root.mainloop()
