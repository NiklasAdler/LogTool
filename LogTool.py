import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog, ttk
import csv
from collections import defaultdict
from datetime import datetime
import configparser

config = configparser.ConfigParser()
config_file = 'config.ini'

if not config.read(config_file):
    config['DEFAULT'] = {
        'LogFilePath': 'sanktionen_log.txt',
        'DefaultExportPath': 'sanktionen_output.csv'
    }
    with open(config_file, 'w') as file:
        config.write(file)

def parse_acp_data(data):
    accounts = []
    seen_entries = set()
    for line in data.strip().split('\n'):
        if line in seen_entries:
            continue
        seen_entries.add(line)
        parts = line.split()
        if len(parts) < 11:
            continue
        total_logins = parts[10].strip('Total Logins:').strip(')')
        try:
            total_logins = int(total_logins)
        except ValueError:
            total_logins = 0
        accounts.append({
            'username': parts[0],
            'account_id': parts[1],
            'socialclub': parts[3],
            'login_date': parts[4] + ' ' + parts[5],
            'first_login_page': parts[7].strip('Page:').strip('()'),
            'total_logins': total_logins
        })
    return accounts

def check_sanctions(accounts):
    account_map = defaultdict(set)
    socialclub_map = defaultdict(list)
    socialclub_to_account_ids = defaultdict(set)
    sanctions_1_1 = {}
    sanctions_1_4 = {}

    for account in accounts:
        account_map[account['account_id']].add(account['socialclub'])
        socialclub_map[account['socialclub']].append(account)
        socialclub_to_account_ids[account['socialclub']].add(account['account_id'])

    # Logik für 1.1-Prüfung
    for account_id, socialclubs in account_map.items():
        if len(socialclubs) > 1:
            for socialclub in socialclubs:
                other_accounts = socialclub_to_account_ids[socialclub] - {account_id}
                if other_accounts:
                    sanctions_1_1[account_id] = {
                        'Regelverstoß': '§1.1',
                        'Account ID': account_id,
                        'Socialclubs': ', '.join(socialclubs),
                        'Sanktion': 'Permanenter Bann'
                    }
                    break

    # Logik für 1.4-Prüfung
    for socialclub, accounts in socialclub_map.items():
        if len(accounts) > 2:
            accounts_sorted_by_logins = sorted(accounts, key=lambda x: x['total_logins'], reverse=True)
            main_account_id = accounts_sorted_by_logins[0]['account_id']
            for acc in accounts:
                if acc['account_id'] == main_account_id:
                    sanction_text = 'Hauptaccount Bann 60 Tage'
                else:
                    sanction_text = 'Permanenter Bann'
                sanctions_1_4[acc['account_id']] = {
                    'Regelverstoß': '§1.4',
                    'Account ID': acc['account_id'],
                    'Socialclubs': ', '.join(account_map[acc['account_id']]),
                    'Sanktion': sanction_text
                }

    return list(sanctions_1_1.values()), list(sanctions_1_4.values())

def show_summary(sanctions_1_1, sanctions_1_4):
    summary = f"Zusammenfassung der Sanktionen:\n\n§1.1 Verstöße: {len(sanctions_1_1)}\n§1.4 Verstöße: {len(sanctions_1_4)}"
    messagebox.showinfo("Zusammenfassung", summary)

def filter_sanctions(sanctions_1_1, sanctions_1_4):
    filter_id = simpledialog.askstring("Filter", "Geben Sie die Account-ID oder Socialclub ein, nach der gefiltert werden soll:")
    if not filter_id:
        return sanctions_1_1, sanctions_1_4

    filtered_1_1 = [s for s in sanctions_1_1 if filter_id in s['Account ID'] or filter_id in s['Socialclubs']]
    filtered_1_4 = [s for s in sanctions_1_4 if filter_id in s['Account ID'] or filter_id in s['Socialclubs']]

    return filtered_1_1, filtered_1_4

def log_action(action):
    log_file_path = config['DEFAULT']['LogFilePath']
    with open(log_file_path, 'a') as log_file:
        log_file.write(f"{datetime.now()} - {action}\n")

def show_sanction_details(sanction):
    details = f"Regelverstoß: {sanction['Regelverstoß']}\nAccount ID: {sanction['Account ID']}\nSocialclubs: {sanction['Socialclubs']}\nSanktion: {sanction['Sanktion']}"
    messagebox.showinfo("Sanktionsdetails", details)

def remove_sanction(sanction_to_remove):
    global sanctions_1_1, sanctions_1_4
    sanctions_1_1 = [s for s in sanctions_1_1 if s != sanction_to_remove]
    sanctions_1_4 = [s for s in sanctions_1_4 if s != sanction_to_remove]
    refresh_gui()

def refresh_gui():
    for widget in scroll_frame.winfo_children():
        widget.destroy()
    check_vars.clear()
    sanction_buttons.clear()
    if sanctions_1_1:
        lbl_1_1 = tk.Label(scroll_frame, text="Sanktionen für §1.1", bg='#e0e0e0', font=('Arial', 12, 'bold'))
        lbl_1_1.pack(anchor='w', pady=(10, 0))
        for sanction in sanctions_1_1:
            var = tk.BooleanVar(value=True)
            check_vars.append((var, sanction))
            frame = tk.Frame(scroll_frame, bg='#ffffff', relief=tk.RAISED, borderwidth=1)
            frame.pack(anchor='w', padx=10, pady=5, fill='x')
            cb = tk.Checkbutton(frame, text=f"{sanction['Account ID']} - {sanction['Regelverstoß']} - Socialclubs: {sanction.get('Socialclubs', 'Unbekannt')}", variable=var, onvalue=True, offvalue=False, bg='#ffffff', font=('Arial', 10))
            cb.pack(side='left', padx=5)
            btn_details = tk.Button(frame, text="Details", command=lambda s=sanction: show_sanction_details(s), font=('Arial', 10), bg='#f0f0f0')
            btn_details.pack(side='left', padx=5)
            btn_remove = tk.Button(frame, text="Entfernen", command=lambda s=sanction: remove_sanction(s), font=('Arial', 10), bg='#f0f0f0')
            btn_remove.pack(side='left', padx=5)
            sanction_buttons.append((btn_details, btn_remove))

    if sanctions_1_4:
        lbl_1_4 = tk.Label(scroll_frame, text="Sanktionen für §1.4", bg='#e0e0e0', font=('Arial', 12, 'bold'))
        lbl_1_4.pack(anchor='w', pady=(10, 0))
        for sanction in sanctions_1_4:
            var = tk.BooleanVar(value=True)
            check_vars.append((var, sanction))
            frame = tk.Frame(scroll_frame, bg='#ffffff', relief=tk.RAISED, borderwidth=1)
            frame.pack(anchor='w', padx=10, pady=5, fill='x')
            cb = tk.Checkbutton(frame, text=f"{sanction['Account ID']} - {sanction['Regelverstoß']} - Socialclubs: {sanction.get('Socialclubs', 'Unbekannt')} - {sanction['Sanktion']}", variable=var, onvalue=True, offvalue=False, fg='red' if 'Permanenter Bann' in sanction['Sanktion'] else 'black', bg='#ffffff', font=('Arial', 10))
            cb.pack(side='left', padx=5)
            btn_details = tk.Button(frame, text="Details", command=lambda s=sanction: show_sanction_details(s), font=('Arial', 10), bg='#f0f0f0')
            btn_details.pack(side='left', padx=5)
            btn_remove = tk.Button(frame, text="Entfernen", command=lambda s=sanction: remove_sanction(s), font=('Arial', 10), bg='#f0f0f0')
            btn_remove.pack(side='left', padx=5)
            sanction_buttons.append((btn_details, btn_remove))

def show_gui_and_select_sanctions(sanctions_1_1_data, sanctions_1_4_data):
    global root, scroll_frame, check_vars, sanction_buttons, sanctions_1_1, sanctions_1_4
    sanctions_1_1 = sanctions_1_1_data
    sanctions_1_4 = sanctions_1_4_data

    root = tk.Tk()
    root.title("Sanktionen auswählen")
    root.configure(background='#e0e0e0')
    
    container = tk.Frame(root, padx=10, pady=10, bg='#e0e0e0')
    container.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(container, bg='#e0e0e0')
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    scroll_frame = tk.Frame(canvas, bg='#e0e0e0')
    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )

    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    check_vars = []
    sanction_buttons = []

    refresh_gui()

    def submit():
        selected_sanctions = []
        for var, sanction in check_vars:
            if var.get():
                selected_sanctions.append(sanction)
        save_sanctions(selected_sanctions)
        log_action("Sanktionen gespeichert und GUI geschlossen")
        root.destroy()

    def export():
        selected_sanctions = []
        for var, sanction in check_vars:
            if var.get():
                selected_sanctions.append(sanction)
        file_types = [('CSV files', '*.csv'), ('All files', '*.*')]
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=file_types)
        if file_path:
            export_sanctions(selected_sanctions, file_path)

    def apply_filter():
        filtered_1_1, filtered_1_4 = filter_sanctions(sanctions_1_1, sanctions_1_4)
        show_gui_and_select_sanctions(filtered_1_1, filtered_1_4)

    submit_button = tk.Button(root, text="Submit", command=submit, relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    submit_button.pack(pady=10, side='left')

    export_button = tk.Button(root, text="Exportieren", command=export, relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    export_button.pack(pady=10, side='left', padx=10)

    filter_button = tk.Button(root, text="Filtern", command=apply_filter, relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    filter_button.pack(pady=10, side='left')

    summary_button = tk.Button(root, text="Zusammenfassung", command=lambda: show_summary(sanctions_1_1, sanctions_1_4), relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    summary_button.pack(pady=10, side='left')

    root.mainloop()

def save_sanctions(selected_sanctions):
    with open(config['DEFAULT']['DefaultExportPath'], 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Regelverstoß', 'Account ID', 'Socialclubs', 'Sanktion']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for sanction in selected_sanctions:
            writer.writerow(sanction)
    log_action("Sanktionen in sanktionen_output.csv gespeichert")
    messagebox.showinfo("Erfolg", "Ausgewählte Sanktionen gespeichert.")

def export_sanctions(sanctions, file_path):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Regelverstoß', 'Account ID', 'Socialclubs', 'Sanktion']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for sanction in sanctions:
            writer.writerow(sanction)
    log_action(f"Sanktionen in {file_path} exportiert")
    messagebox.showinfo("Erfolg", f"Sanktionen in {file_path} exportiert.")

try:
    with open('acp_data.txt', 'r') as file:
        acp_data = file.read()
    accounts = parse_acp_data(acp_data)
    sanctions_1_1_data, sanctions_1_4_data = check_sanctions(accounts)

    if sanctions_1_1_data or sanctions_1_4_data:
        log_action("GUI zur Auswahl der Sanktionen gestartet")
        show_gui_and_select_sanctions(sanctions_1_1_data, sanctions_1_4_data)
    else:
        messagebox.showinfo("Information", "Keine Regelbrüche festgestellt.")
        log_action("Keine Regelbrüche festgestellt")
except Exception as e:
    messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {e}")
    log_action(f"Fehler aufgetreten: {e}")
