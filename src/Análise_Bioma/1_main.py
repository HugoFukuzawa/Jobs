import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import os

# Caminho completo do Python no ambiente virtual
python_executable = r"C:\Users\HUGO\PycharmProjects\Projeto_Geral\venv\Scripts\python.exe"

# Lista com o caminho dos scripts
scripts = [
    r"C:\Users\HUGO\PycharmProjects\Projeto_Geral\src\Análise_Bioma\3 RGB_to_PNG.py",
    r"C:\Users\HUGO\PycharmProjects\Projeto_Geral\src\Análise_Bioma\4 Combination.py",
    r"C:\Users\HUGO\PycharmProjects\Projeto_Geral\src\Análise_Bioma\4 Gif.py",
    r"C:\Users\HUGO\PycharmProjects\Projeto_Geral\src\Análise_Bioma\5 TimeSeries_NDVI.py",
    r"C:\Users\HUGO\PycharmProjects\Projeto_Geral\src\Análise_Bioma\3 NDVI_to_PNG.py",
    r"C:\Users\HUGO\PycharmProjects\Projeto_Geral\src\Análise_Bioma\main.py"
]

process = None

# Funções para gerenciar a execução do script e a leitura do output e error
def read_output(process, output_text):
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            output_text.config(state="normal")  # Habilita para inserção de texto
            output_text.insert(tk.END, output)
            output_text.see(tk.END)
            output_text.config(state="disabled")  # Desabilita para impedir a edição do usuário
    process.stdout.close()

def read_error(process, output_text):
    while True:
        error = process.stderr.readline()
        if error == '' and process.poll() is not None:
            break
        if error:
            output_text.config(state="normal")  # Habilita para inserção de texto
            output_text.insert(tk.END, "ERRO: " + error)
            output_text.see(tk.END)
            output_text.config(state="disabled")  # Desabilita para impedir a edição do usuário
    process.stderr.close()

def send_input():
    user_input = input_entry.get()
    input_entry.delete(0, tk.END)
    if process and process.stdin:
        process.stdin.write(user_input + "\n")
        process.stdin.flush()

def run_script(script_path):
    global process
    if not os.path.exists(python_executable):
        messagebox.showerror("Erro", f"O executável do Python não foi encontrado: {python_executable}")
        return
    if not os.path.exists(script_path):
        messagebox.showerror("Erro", f"O script não foi encontrado: {script_path}")
        return

    try:
        process = subprocess.Popen(
            [python_executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        output_thread = threading.Thread(target=read_output, args=(process, output_text))
        error_thread = threading.Thread(target=read_error, args=(process, output_text))
        output_thread.start()
        error_thread.start()
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao executar {script_path}.\n{e}")

def on_closing():
    global process
    if process:
        process.terminate()
        process = None
    root.destroy()

# Configuração da interface tkinter
root = tk.Tk()
root.title("Executor de Scripts Python com Terminal Interativo")
root.geometry("700x600")

# Título
label = tk.Label(root, text="Selecione um script para executar:", font=("Arial", 12))
label.pack(pady=(10, 5))

# Frame para o Listbox com barra de rolagem
listbox_frame = tk.Frame(root)
listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

# Listbox com barra de rolagem
script_listbox = tk.Listbox(listbox_frame, font=("Arial", 10), selectmode=tk.SINGLE)
scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=script_listbox.yview)
script_listbox.config(yscrollcommand=scrollbar.set)

scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
script_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

for script in scripts:
    script_listbox.insert(tk.END, os.path.basename(script))

# Área de texto para mostrar o output do script (somente leitura)
output_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Arial", 10), height=10)
output_text.config(state="disabled")  # Define como apenas leitura
output_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

# Entrada de texto para enviar comandos ao script
input_label = tk.Label(root, text="Digite a entrada para o script:", font=("Arial", 10))
input_label.pack()

input_entry = tk.Entry(root, font=("Arial", 10))
input_entry.pack(fill=tk.X, padx=20, pady=5)

# Botão para enviar a entrada ao subprocesso
input_button = tk.Button(root, text="Enviar Entrada", command=send_input)
input_button.pack(pady=5)

# Botão para iniciar a execução do script selecionado
def on_execute_button_click():
    selected_index = script_listbox.curselection()
    if selected_index:
        script_path = scripts[selected_index[0]]
        run_script(script_path)
    else:
        messagebox.showwarning("Atenção", "Selecione um script para executar.")

execute_button = tk.Button(root, text="Executar Script", command=on_execute_button_click, font=("Arial", 10), width=20)
execute_button.pack(pady=(0, 20))

# Define o evento para fechamento da janela
root.protocol("WM_DELETE_WINDOW", on_closing)

# Iniciar o loop principal
root.mainloop()
