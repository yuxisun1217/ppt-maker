"""Login and registration windows."""
import tkinter as tk
from tkinter import ttk, messagebox


class LoginWindow:
    def __init__(self, on_login_success):
        self.on_login_success = on_login_success
        self.user = None

        self.root = tk.Tk()
        self.root.title('会议串场PPT生成器 - 登录')
        self.root.geometry('380x320')
        self.root.resizable(False, False)
        self.root.configure(bg='#E3F2FD')
        self._center_window(self.root)

        self._build()

    def _center_window(self, win):
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f'+{(sw-w)//2}+{(sh-h)//2}')

    def _build(self):
        f = tk.Frame(self.root, bg='#E3F2FD', padx=30, pady=20)
        f.pack(expand=True, fill='both')

        tk.Label(f, text='会议串场PPT生成器', font=('Microsoft YaHei', 16, 'bold'),
                 bg='#E3F2FD', fg='#1976D2').pack(pady=(10, 20))

        tk.Label(f, text='用户名', bg='#E3F2FD', fg='#333',
                 font=('Microsoft YaHei', 10)).pack(anchor='w')
        self.entry_user = tk.Entry(f, font=('Microsoft YaHei', 11), width=30)
        self.entry_user.pack(pady=(2, 10), ipady=3)

        tk.Label(f, text='密码', bg='#E3F2FD', fg='#333',
                 font=('Microsoft YaHei', 10)).pack(anchor='w')
        self.entry_pwd = tk.Entry(f, font=('Microsoft YaHei', 11), width=30, show='*')
        self.entry_pwd.pack(pady=(2, 10), ipady=3)

        btn_frame = tk.Frame(f, bg='#E3F2FD')
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text='登  录', font=('Microsoft YaHei', 11),
                  bg='#1976D2', fg='white', width=12, height=1,
                  activebackground='#1565C0', activeforeground='white',
                  relief='flat', cursor='hand2',
                  command=self._login).pack(side='left', padx=5)
        tk.Button(btn_frame, text='注册新账号', font=('Microsoft YaHei', 11),
                  bg='#BBDEFB', fg='#1976D2', width=12, height=1,
                  activebackground='#90CAF9', relief='flat', cursor='hand2',
                  command=self._open_register).pack(side='left', padx=5)

        self.status_var = tk.StringVar()
        tk.Label(f, textvariable=self.status_var, bg='#E3F2FD', fg='#F44336',
                 font=('Microsoft YaHei', 9)).pack(pady=5)

        self.root.bind('<Return>', lambda e: self._login())
        self.entry_user.focus_set()

    def _login(self):
        from database.db import authenticate
        username = self.entry_user.get().strip()
        password = self.entry_pwd.get().strip()
        if not username or not password:
            self.status_var.set('请输入用户名和密码')
            return
        user = authenticate(username, password)
        if user:
            self.user = user
            self.root.destroy()
            self.on_login_success(user)
        else:
            self.status_var.set('用户名或密码错误')

    def _open_register(self):
        self.root.withdraw()
        RegisterWindow(self.root, self._on_register_done)

    def _on_register_done(self):
        self.root.deiconify()
        self.entry_pwd.delete(0, 'end')

    def run(self):
        self.root.mainloop()


class RegisterWindow:
    def __init__(self, parent, on_close):
        self.parent = parent
        self.on_close = on_close

        self.win = tk.Toplevel(parent)
        self.win.title('注册新账号')
        self.win.geometry('380x420')
        self.win.resizable(False, False)
        self.win.configure(bg='#E3F2FD')

        self._build()
        self._center()

    def _center(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f'+{(sw-w)//2}+{(sh-h)//2}')

    def _build(self):
        f = tk.Frame(self.win, bg='#E3F2FD', padx=30, pady=20)
        f.pack(expand=True, fill='both')

        tk.Label(f, text='注册新账号', font=('Microsoft YaHei', 14, 'bold'),
                 bg='#E3F2FD', fg='#1976D2').pack(pady=(5, 15))

        fields = [
            ('用户名 *', 'user', None),
            ('密码 *', 'pwd', '*'),
            ('确认密码 *', 'pwd2', '*'),
            ('DeepSeek API Key', 'apikey', None),
        ]
        self.entries = {}
        for label, key, show in fields:
            tk.Label(f, text=label, bg='#E3F2FD', fg='#333',
                     font=('Microsoft YaHei', 10)).pack(anchor='w')
            e = tk.Entry(f, font=('Microsoft YaHei', 11), width=30,
                         show=show if show else '')
            e.pack(pady=(2, 6), ipady=3)
            self.entries[key] = e

        self.status_var = tk.StringVar()
        tk.Label(f, textvariable=self.status_var, bg='#E3F2FD', fg='#F44336',
                 font=('Microsoft YaHei', 9)).pack(pady=2)

        btn_frame = tk.Frame(f, bg='#E3F2FD')
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text='保  存', font=('Microsoft YaHei', 11),
                  bg='#1976D2', fg='white', width=12, relief='flat', cursor='hand2',
                  command=self._register).pack(side='left', padx=5)
        tk.Button(btn_frame, text='取  消', font=('Microsoft YaHei', 11),
                  bg='#BBDEFB', fg='#1976D2', width=12, relief='flat', cursor='hand2',
                  command=self._close).pack(side='left', padx=5)

    def _register(self):
        from database.db import create_user
        username = self.entries['user'].get().strip()
        pwd = self.entries['pwd'].get().strip()
        pwd2 = self.entries['pwd2'].get().strip()
        apikey = self.entries['apikey'].get().strip()

        if not username or not pwd:
            self.status_var.set('用户名和密码为必填项')
            return
        if pwd != pwd2:
            self.status_var.set('两次输入的密码不一致')
            return

        uid = create_user(username, pwd, apikey)
        if uid:
            messagebox.showinfo('成功', f'账号 "{username}" 注册成功，请登录。')
            self._close()
        else:
            self.status_var.set('用户名已存在，请更换')

    def _close(self):
        self.win.destroy()
        self.on_close()
