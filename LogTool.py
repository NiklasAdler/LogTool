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
    seen_entries = {}
    
    for line in data.strip().split('\n'):
        parts = line.split()
        if len(parts) < 11:
            continue
        total_logins = parts[-1].strip('Total Logins:').strip(')')
        try:
            total_logins = int(total_logins)
        except ValueError:
            total_logins = 0

        key = (parts[0], parts[1], parts[3], parts[4] + ' ' + parts[5])

        if key in seen_entries:
            if seen_entries[key]['total_logins'] != total_logins:
                seen_entries[key]['total_logins'] += total_logins
        else:
            seen_entries[key] = {
                'username': parts[0],
                'account_id': parts[1],
                'socialclub': parts[3],
                'login_date': parts[4] + ' ' + parts[5],
                'first_login_page': parts[7].strip('Page:').strip('()'),
                'total_logins': total_logins
            }

    accounts = list(seen_entries.values())
    return accounts

def check_sanctions(accounts):
    account_map = defaultdict(set)
    socialclub_map = defaultdict(list)
    socialclub_to_account_ids = defaultdict(set)
    sanctions_1_1 = {}
    sanctions_1_4 = defaultdict(list)
    combined_sanctions = []

    # Accounts und Social Clubs zuordnen
    for account in accounts:
        account_map[account['account_id']].add(account['socialclub'])
        socialclub_map[account['socialclub']].append(account)
        socialclub_to_account_ids[account['socialclub']].add(account['account_id'])

    # Logik für §1.1-Prüfung (Social Club mit mehreren Account-IDs)
    for account_id, socialclubs in account_map.items():
        if len(socialclubs) > 1:
            # Prüfen, ob ein anderer Account diese Social Clubs verwendet
            for socialclub in socialclubs:
                other_accounts = socialclub_to_account_ids[socialclub] - {account_id}
                if other_accounts:
                    sanctions_1_1[account_id] = {
                        'Regelverstoß': '§1.1 - Mehrere Social Clubs für einen Account',
                        'Account ID': account_id,
                        'Benutzername': accounts[0]['username'],
                        'Socialclubs': ', '.join(socialclubs),
                        'Sanktion': 'Permanenter Bann'
                    }
                    break

    # Logik für §1.4-Prüfung (Mehrere Accounts mit einem Social Club)
    for socialclub, accounts in socialclub_map.items():
        if len(accounts) > 2:
            accounts_sorted_by_logins = sorted(accounts, key=lambda x: x['total_logins'], reverse=True)
            main_account_id = accounts_sorted_by_logins[0]['account_id']
            for acc in accounts:
                if acc['account_id'] == main_account_id:
                    sanction_text = f'Hauptaccount Bann 60 Tage (Logins: {acc["total_logins"]})'
                else:
                    sanction_text = f'Permanenter Bann (Logins: {acc["total_logins"]})'
                sanctions_1_4[socialclub].append({
                    'Regelverstoß': '§1.4 - Mehrere Accounts mit einem Social Club',
                    'Account ID': acc['account_id'],
                    'Benutzername': acc['username'],
                    'Socialclubs': acc['socialclub'],
                    'Sanktion': sanction_text
                })

    already_combined_ids = set()
    combined_sanctions_map = {}

    # Kombinierte Sanktionen
    for account_id, sanction_1_1 in list(sanctions_1_1.items()):
        for socialclub, sanctions in list(sanctions_1_4.items()):
            for sanction_1_4 in sanctions:
                if sanction_1_4['Account ID'] == account_id:
                    combined_key = (account_id, sanction_1_1['Socialclubs'])
                    if combined_key not in combined_sanctions_map:
                        combined_sanctions_map[combined_key] = {
                            'Regelverstoß': sanction_1_1['Regelverstoß'] + ' + ' + sanction_1_4['Regelverstoß'],
                            'Account ID': account_id,
                            'Benutzername': sanction_1_1['Benutzername'],
                            'Socialclubs': sanction_1_1['Socialclubs'],
                            'Sanktion': combine_sanctions(sanction_1_1['Sanktion'], sanction_1_4['Sanktion'])
                        }
                    already_combined_ids.add(account_id)
                    break

    combined_sanctions = list(combined_sanctions_map.values())

    sanctions_1_1 = [s for s in sanctions_1_1.values() if s['Account ID'] not in already_combined_ids]
    # Hinweis: §1.4-Fälle werden hier nicht entfernt, sie bleiben in der GUI sichtbar

    return sanctions_1_1, sanctions_1_4, combined_sanctions

def combine_sanctions(sanction_1_1, sanction_1_4):
    # Logik, um sicherzustellen, dass die kombinierte Sanktion immer ein permanenter Bann ist
    if sanction_1_1 == sanction_1_4:
        return sanction_1_1
    
    if "Permanenter Bann" in sanction_1_1 and "Permanenter Bann" in sanction_1_4:
        logins_1_1 = int(sanction_1_1.split("Logins:")[1].strip(')').strip()) if "Logins:" in sanction_1_1 else 0
        logins_1_4 = int(sanction_1_4.split("Logins:")[1].strip(')').strip()) if "Logins:" in sanction_1_4 else 0
        combined_logins = logins_1_1 + logins_1_4
        return f'Permanenter Bann (Logins: {combined_logins})'
    
    # Wenn einer der beiden Texte ein 60-Tage-Bann ist, wird dies zu einem permanenten Bann konvertiert
    if "Hauptaccount Bann 60 Tage" in sanction_1_1 or "Hauptaccount Bann 60 Tage" in sanction_1_4:
        return 'Permanenter Bann'
    
    return f"Permanenter Bann"

def show_summary(sanctions_1_1, sanctions_1_4, combined_sanctions):
    summary = (
        f"Zusammenfassung der Sanktionen:\n\n"
        f"§1.1 Verstöße: {len(sanctions_1_1)}\n"
        f"§1.4 Verstöße: {sum(len(v) for v in sanctions_1_4.values())}\n"
        f"Kombinierte Verstöße (§1.1 und §1.4): {len(combined_sanctions)}"
    )
    messagebox.showinfo("Zusammenfassung", summary)

def apply_filter():
    global sanctions_1_1, sanctions_1_4, combined_sanctions
    filter_id = simpledialog.askstring("Filter", "Geben Sie die Account-ID oder Socialclub ein, nach der gefiltert werden soll:")
    if not filter_id:
        return

    filtered_1_1, filtered_1_4 = filter_sanctions(sanctions_1_1, sanctions_1_4, filter_id)
    filtered_combined = [s for s in combined_sanctions if filter_id in s['Account ID'] or filter_id in s['Socialclubs']]

    sanctions_1_1 = filtered_1_1
    sanctions_1_4 = filtered_1_4
    combined_sanctions = filtered_combined
    refresh_gui()

def filter_sanctions(sanctions_1_1, sanctions_1_4, filter_id):
    filtered_1_1 = [s for s in sanctions_1_1 if filter_id in s['Account ID'] or filter_id in s['Socialclubs']]
    filtered_1_4 = defaultdict(list)
    for socialclub, sanctions in sanctions_1_4.items():
        filtered_sanctions = [s for s in sanctions if filter_id in s['Account ID'] or filter_id in s['Socialclubs']]
        if filtered_sanctions:
            filtered_1_4[socialclub] = filtered_sanctions

    return filtered_1_1, filtered_1_4

def log_action(action):
    log_file_path = config['DEFAULT']['LogFilePath']
    with open(log_file_path, 'a') as log_file:
        log_file.write(f"{datetime.now()} - {action}\n")

def show_sanction_details(sanction):
    details = f"Regelverstoß: {sanction['Regelverstoß']}\nAccount ID: {sanction['Account ID']}\nBenutzername: {sanction['Benutzername']}\nSocialclubs: {sanction['Socialclubs']}\nSanktion: {sanction['Sanktion']}"
    messagebox.showinfo("Sanktionsdetails", details)

def remove_sanction(socialclub, sanction_to_remove):
    global sanctions_1_1, sanctions_1_4, combined_sanctions
    if socialclub:
        sanctions_1_4[socialclub] = [s for s in sanctions_1_4[socialclub] if s != sanction_to_remove]
        if not sanctions_1_4[socialclub]:
            del sanctions_1_4[socialclub]
    else:
        combined_sanctions = [s for s in combined_sanctions if s != sanction_to_remove]
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
            btn_remove = tk.Button(frame, text="Entfernen", command=lambda s=sanction: remove_sanction(None, s), font=('Arial', 10), bg='#f0f0f0')
            btn_remove.pack(side='left', padx=5)
            sanction_buttons.append((btn_details, btn_remove))

    if sanctions_1_4:
        lbl_1_4 = tk.Label(scroll_frame, text="Sanktionen für §1.4", bg='#e0e0e0', font=('Arial', 12, 'bold'))
        lbl_1_4.pack(anchor='w', pady=(10, 0))
        for socialclub, sanctions in sanctions_1_4.items():
            lbl_socialclub = tk.Label(scroll_frame, text=f"Socialclub: {socialclub}", bg='#d0d0d0', font=('Arial', 11, 'bold'))
            lbl_socialclub.pack(anchor='w', pady=(5, 0), padx=20)
            for sanction in sanctions:
                var = tk.BooleanVar(value=True)
                check_vars.append((var, sanction))
                frame = tk.Frame(scroll_frame, bg='#ffffff', relief=tk.RAISED, borderwidth=1)
                frame.pack(anchor='w', padx=10, pady=5, fill='x')
                cb = tk.Checkbutton(frame, text=f"{sanction['Account ID']} - {sanction['Regelverstoß']} - {sanction['Sanktion']}", variable=var, onvalue=True, offvalue=False, fg='red' if 'Permanenter Bann' in sanction['Sanktion'] else 'black', bg='#ffffff', font=('Arial', 10))
                cb.pack(side='left', padx=5)
                btn_details = tk.Button(frame, text="Details", command=lambda s=sanction: show_sanction_details(s), font=('Arial', 10), bg='#f0f0f0')
                btn_details.pack(side='left', padx=5)
                btn_remove = tk.Button(frame, text="Entfernen", command=lambda s=sanction: remove_sanction(socialclub, s), font=('Arial', 10), bg='#f0f0f0')
                btn_remove.pack(side='left', padx=5)
                sanction_buttons.append((btn_details, btn_remove))

    if combined_sanctions:
        lbl_combined = tk.Label(scroll_frame, text="Kombinierte Sanktionen für §1.1 und §1.4", bg='#e0e0e0', font=('Arial', 12, 'bold'))
        lbl_combined.pack(anchor='w', pady=(10, 0))
        for sanction in combined_sanctions:
            var = tk.BooleanVar(value=True)
            check_vars.append((var, sanction))
            frame = tk.Frame(scroll_frame, bg='#ffffff', relief=tk.RAISED, borderwidth=1)
            frame.pack(anchor='w', padx=10, pady=5, fill='x')
            cb = tk.Checkbutton(frame, text=f"{sanction['Account ID']} - {sanction['Regelverstoß']} - Socialclubs: {sanction.get('Socialclubs', 'Unbekannt')}", variable=var, onvalue=True, offvalue=False, fg='blue', bg='#ffffff', font=('Arial', 10))
            cb.pack(side='left', padx=5)
            btn_details = tk.Button(frame, text="Details", command=lambda s=sanction: show_sanction_details(s), font=('Arial', 10), bg='#f0f0f0')
            btn_details.pack(side='left', padx=5)
            btn_remove = tk.Button(frame, text="Entfernen", command=lambda s=sanction: remove_sanction(None, s), font=('Arial', 10), bg='#f0f0f0')
            btn_remove.pack(side='left', padx=5)
            sanction_buttons.append((btn_details, btn_remove))

def reload_data():
    try:
        with open('acp_data.txt', 'r') as file:
            acp_data = file.read()
        accounts = parse_acp_data(acp_data)
        global sanctions_1_1, sanctions_1_4, combined_sanctions
        sanctions_1_1, sanctions_1_4, combined_sanctions = check_sanctions(accounts)
        refresh_gui()
        log_action("Daten neu eingelesen und GUI aktualisiert")
    except Exception as e:
        messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {e}")
        log_action(f"Fehler aufgetreten: {e}")

def show_gui_and_select_sanctions(sanctions_1_1_data, sanctions_1_4_data, combined_sanctions_data):
    global root, scroll_frame, check_vars, sanction_buttons, sanctions_1_1, sanctions_1_4, combined_sanctions
    sanctions_1_1 = sanctions_1_1_data
    sanctions_1_4 = sanctions_1_4_data
    combined_sanctions = combined_sanctions_data

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

    submit_button = tk.Button(root, text="Submit", command=submit, relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    submit_button.pack(pady=10, side='left')

    export_button = tk.Button(root, text="Exportieren", command=export_sanctions_command, relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    export_button.pack(pady=10, side='left', padx=10)

    filter_button = tk.Button(root, text="Filtern", command=apply_filter, relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    filter_button.pack(pady=10, side='left')

    reload_button = tk.Button(root, text="Daten neu laden", command=reload_data, relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    reload_button.pack(pady=10, side='left')

    summary_button = tk.Button(root, text="Zusammenfassung", command=lambda: show_summary(sanctions_1_1, sanctions_1_4, combined_sanctions), relief=tk.RAISED, borderwidth=2, font=('Arial', 12), bg='#d0d0d0')
    summary_button.pack(pady=10, side='left')

    root.mainloop()

def submit():
    selected_sanctions = []
    selected_ids = set()
    for var, sanction in check_vars:
        if var.get():
            if sanction['Account ID'] not in selected_ids:
                selected_sanctions.append(sanction)
                selected_ids.add(sanction['Account ID'])
    selected_sanctions.extend(combined_sanctions)  # Füge kombinierte Sanktionen hinzu
    save_sanctions(selected_sanctions)
    log_action("Sanktionen gespeichert und GUI geschlossen")
    root.destroy()

def save_sanctions(selected_sanctions):
    with open(config['DEFAULT']['DefaultExportPath'], 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Regelverstoß', 'Account ID', 'Benutzername', 'Socialclubs', 'Sanktion']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for sanction in selected_sanctions:
            writer.writerow(sanction)
    log_action("Sanktionen in sanktionen_output.csv gespeichert")
    messagebox.showinfo("Erfolg", "Ausgewählte Sanktionen gespeichert.")

def export_sanctions_command():
    selected_sanctions = []
    selected_ids = set()
    for var, sanction in check_vars:
        if var.get():
            if sanction['Account ID'] not in selected_ids:
                selected_sanctions.append(sanction)
                selected_ids.add(sanction['Account ID'])
    selected_sanctions.extend(combined_sanctions)  # Füge kombinierte Sanktionen hinzu
    if not selected_sanctions:
        messagebox.showinfo("Keine Auswahl", "Es wurden keine Sanktionen ausgewählt.")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
    if file_path:
        export_sanctions(selected_sanctions, file_path)

def export_sanctions(sanctions, file_path):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Regelverstoß', 'Account ID', 'Benutzername', 'Socialclubs', 'Sanktion']
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
    sanctions_1_1_data, sanctions_1_4_data, combined_sanctions_data = check_sanctions(accounts)

    if sanctions_1_1_data or sanctions_1_4_data or combined_sanctions_data:
        log_action("GUI zur Auswahl der Sanktionen gestartet")
        show_gui_and_select_sanctions(sanctions_1_1_data, sanctions_1_4_data, combined_sanctions_data)
    else:
        messagebox.showinfo("Information", "Keine Regelbrüche festgestellt.")
        log_action("Keine Regelbrüche festgestellt")
except Exception as e:
    messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {e}")
    log_action(f"Fehler aufgetreten: {e}")
