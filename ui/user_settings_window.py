"""User account settings window — edit profile and change password."""
import tkinter as tk
from tkinter import messagebox


class UserSettingsWindow:
    """Modal window for the logged-in user to edit their account details."""

    def __init__(self, parent, user: dict, on_save):
        """
        parent   — parent tk widget
        user     — current user dict (id, username, api_key, ocr_api_key)
        on_save  — callback(updated_user_dict) when save succeeds
        """
        self.parent = parent
        self.user = user
        self.on_save = on_save

        self.win = tk.Toplevel(parent)
        self.win.title('账户设置')
        self.win.geometry('440x580')
        self.win.resizable(True, True)
        self.win.minsize(400, 520)
        self.win.configure(bg='#E3F2FD')
        self.win.transient(parent)
        self._center()

        self._build()

    def _center(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f'+{(sw - w) // 2}+{(sh - h) // 2}')

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self):
        f = tk.Frame(self.win, bg='#E3F2FD', padx=30, pady=20)
        f.pack(expand=True, fill='both')

        tk.Label(f, text='账户设置', font=('Microsoft YaHei', 14, 'bold'),
                 bg='#E3F2FD', fg='#1976D2').pack(pady=(0, 15))

        self.entries = {}

        # --- Profile fields ---
        self._add_field(f, '用户名', 'username', self.user.get('username', ''))
        self._add_field(f, 'DeepSeek API Key', 'api_key', self.user.get('api_key', ''))
        self._add_field(f, 'OCR.space API Key', 'ocr_api_key',
                        self.user.get('ocr_api_key', ''))

        # --- Separator ---
        tk.Frame(f, bg='#BBDEFB', height=1).pack(fill='x', pady=(14, 10))
        tk.Label(f, text='修改密码（留空则不修改）', font=('Microsoft YaHei', 10, 'bold'),
                 bg='#E3F2FD', fg='#1976D2').pack(anchor='w', pady=(0, 6))

        self._add_field(f, '当前密码', 'cur_pwd', '', show='*')
        self._add_field(f, '新密码', 'new_pwd', '', show='*')
        self._add_field(f, '确认新密码', 'new_pwd2', '', show='*')

        # --- Status ---
        self.status_var = tk.StringVar()
        tk.Label(f, textvariable=self.status_var, bg='#E3F2FD', fg='#F44336',
                 font=('Microsoft YaHei', 9)).pack(pady=(6, 2))

        # --- Buttons ---
        btn_frame = tk.Frame(f, bg='#E3F2FD')
        btn_frame.pack(pady=(10, 0))
        tk.Button(btn_frame, text='保  存', font=('Microsoft YaHei', 11),
                  bg='#1976D2', fg='white', width=12, relief='flat', cursor='hand2',
                  command=self._save).pack(side='left', padx=5)
        tk.Button(btn_frame, text='取  消', font=('Microsoft YaHei', 11),
                  bg='#BBDEFB', fg='#1976D2', width=12, relief='flat', cursor='hand2',
                  command=self.win.destroy).pack(side='left', padx=5)

    def _add_field(self, parent, label, key, default_value, show=None):
        tk.Label(parent, text=label, bg='#E3F2FD', fg='#333',
                 font=('Microsoft YaHei', 10)).pack(anchor='w')
        e = tk.Entry(parent, font=('Microsoft YaHei', 11), width=36,
                     show=show if show else '')
        e.insert(0, default_value)
        e.pack(pady=(2, 6), ipady=3)
        self.entries[key] = e

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

    def _save(self):
        from database.db import update_user, update_password, authenticate

        user_id = self.user['id']
        new_username = self.entries['username'].get().strip()
        new_api_key = self.entries['api_key'].get().strip()
        new_ocr_api_key = self.entries['ocr_api_key'].get().strip()
        cur_pwd = self.entries['cur_pwd'].get().strip()
        new_pwd = self.entries['new_pwd'].get().strip()
        new_pwd2 = self.entries['new_pwd2'].get().strip()

        if not new_username:
            self.status_var.set('用户名不能为空')
            return

        # Password change requested
        if new_pwd or new_pwd2 or cur_pwd:
            if not cur_pwd:
                self.status_var.set('请先输入当前密码')
                return
            if not new_pwd:
                self.status_var.set('请输入新密码')
                return
            if new_pwd != new_pwd2:
                self.status_var.set('两次输入的新密码不一致')
                return
            # Verify current password
            verified = authenticate(self.user['username'], cur_pwd)
            if verified is None:
                self.status_var.set('当前密码错误')
                return
            update_password(user_id, new_pwd)

        # Update profile
        ok = update_user(user_id, new_username, new_api_key, new_ocr_api_key)
        if not ok:
            self.status_var.set('用户名已被占用，请更换')
            return

        # Build updated user dict and notify
        updated_user = {
            'id': user_id,
            'username': new_username,
            'api_key': new_api_key,
            'ocr_api_key': new_ocr_api_key,
        }
        self.on_save(updated_user)
        messagebox.showinfo('成功', '账户信息已更新。', parent=self.win)
        self.win.destroy()
