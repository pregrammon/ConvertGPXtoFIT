# -*- coding: utf-8 -*-
"""GPX 转 FIT 转换器 —— tkinter 桌面版。

用法：python main.py
"""
import os
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import gpxpy

from converter import gpx_to_fit, load_gpx

APP_TITLE = 'GPX 转 FIT 转换器'


class Gpx2FitApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry('640x520')
        root.minsize(520, 460)

        self.files = []          # 已选择的 GPX 文件路径列表
        self.out_dir = ''        # 输出目录（空=与源文件同目录）
        self.converting = False

        self._build_ui()

    def _build_ui(self):
        pad = {'padx': 10, 'pady': 6}
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill='both', expand=True)

        # 标题
        ttk.Label(frame, text=APP_TITLE, font=('', 16, 'bold')).pack(anchor='w', **pad)

        # 添加 / 移除文件
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill='x', **pad)
        ttk.Button(btn_row, text='添加 GPX 文件...', command=self._add_files).pack(side='left')
        ttk.Button(btn_row, text='移除选中', command=self._remove_selected).pack(side='left', padx=6)
        ttk.Button(btn_row, text='清空', command=self._clear_files).pack(side='left')

        # 文件列表
        ttk.Label(frame, text='已选择的文件（双击条目可移除）：').pack(anchor='w', **pad)
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True, **pad)
        self.listbox = tk.Listbox(list_frame, height=10)
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.listbox.bind('<Double-Button-1>', lambda e: self._remove_selected())

        # 输出目录
        dir_row = ttk.Frame(frame)
        dir_row.pack(fill='x', **pad)
        ttk.Label(dir_row, text='输出目录（留空则与源文件同目录）：').pack(anchor='w')
        self.out_var = tk.StringVar()
        ttk.Entry(dir_row, textvariable=self.out_var).pack(side='left', fill='x', expand=True, padx=(0, 6))
        ttk.Button(dir_row, text='浏览...', command=self._choose_out_dir).pack(side='left')

        # 转换按钮 + 进度
        self.convert_btn = ttk.Button(frame, text='开始转换', command=self._start_convert)
        self.convert_btn.pack(fill='x', **pad)

        self.progress = ttk.Progressbar(frame, mode='determinate', maximum=100)
        self.progress.pack(fill='x', **pad)

        self.status_var = tk.StringVar(value='就绪')
        ttk.Label(frame, textvariable=self.status_var, foreground='#555').pack(anchor='w', **pad)

    # ---------- 事件处理 ----------
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title='选择 GPX 文件',
            filetypes=[('GPX 文件', '*.gpx'), ('所有文件', '*.*')],
        )
        added = 0
        for p in paths:
            if p.lower().endswith('.gpx') and p not in self.files:
                self.files.append(p)
                added += 1
            elif not p.lower().endswith('.gpx'):
                messagebox.showwarning('提示', f'已忽略非 GPX 文件：\n{p}')
        if added and not self.out_dir:
            self.out_dir = os.path.dirname(self.files[0])
            self.out_var.set(self.out_dir)
        self._refresh_list()

    def _remove_selected(self):
        sel = list(self.listbox.curselection())
        for i in reversed(sel):
            self.files.pop(i)
        self._refresh_list()

    def _clear_files(self):
        self.files.clear()
        self._refresh_list()

    def _choose_out_dir(self):
        d = filedialog.askdirectory(title='选择输出目录')
        if d:
            self.out_dir = d
            self.out_var.set(d)

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.files:
            self.listbox.insert(tk.END, p)
        self.status_var.set(f'已选择 {len(self.files)} 个文件')

    # ---------- 转换 ----------
    def _start_convert(self):
        if self.converting:
            return
        if not self.files:
            messagebox.showwarning('提示', '请先添加 GPX 文件')
            return

        self.converting = True
        self.convert_btn.config(state='disabled')
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.files)
        self.status_var.set('开始转换...')

        t = threading.Thread(target=self._convert_worker, daemon=True)
        t.start()

    def _convert_worker(self):
        ok = 0
        errors = []
        total = len(self.files)
        for i, src in enumerate(self.files, start=1):
            try:
                gpx = load_gpx(src)
                fit_file = gpx_to_fit(gpx)
                out_path = self._unique_out_path(src)
                fit_file.to_file(out_path)
                ok += 1
                self.root.after(0, self._set_status, f'({i}/{total}) 完成：{os.path.basename(out_path)}')
            except Exception as e:
                errors.append((os.path.basename(src), str(e)))
            self.root.after(0, self._set_progress, i)

        self.root.after(0, self._finish, ok, errors, total)

    def _unique_out_path(self, src):
        base = os.path.splitext(os.path.basename(src))[0]
        out_dir = self.out_dir if self.out_dir else os.path.dirname(src)
        candidate = os.path.join(out_dir, base + '.fit')
        n = 1
        while os.path.exists(candidate):
            candidate = os.path.join(out_dir, f'{base}-{n}.fit')
            n += 1
        return candidate

    def _set_progress(self, value):
        self.progress['value'] = value

    def _set_status(self, text):
        self.status_var.set(text)

    def _finish(self, ok, errors, total):
        self.converting = False
        self.convert_btn.config(state='normal')
        self.progress['value'] = total
        if errors:
            msg = '\n'.join(f'{n}：{e}' for n, e in errors)
            self.status_var.set(f'完成 {ok}/{total}，{len(errors)} 个失败')
            messagebox.showwarning('转换结果', f'成功 {ok}/{total} 个文件。\n\n失败：\n{msg}')
        else:
            self.status_var.set(f'全部完成，共 {ok} 个文件')
            messagebox.showinfo('转换结果', f'成功转换 {ok} 个文件。')


def main():
    root = tk.Tk()
    app = Gpx2FitApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
