import os
import json
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

# Configurações de e-mail
EMAIL = "elieserjunior97@gmail.com"
SENHA = "#elieserjredhara1822"  # Substitua pela sua senha de aplicativo

# Caminho do arquivo JSON
CAMINHO_ARQUIVO = os.path.join(os.getcwd(), "agendamentos.json")

# Função para carregar os agendamentos
def carregar_agendamentos():
    try:
        with open(CAMINHO_ARQUIVO, "r") as f:
            data = json.load(f)
            # Reconverter chaves de string para tupla
            return {tuple(eval(k)): v for k, v in data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Função para salvar os agendamentos
def salvar_agendamentos(agendamentos):
    try:
        # Converter chaves de tupla para string
        agendamentos_serializado = {str(k): v for k, v in agendamentos.items()}
        with open(CAMINHO_ARQUIVO, "w") as f:
            json.dump(agendamentos_serializado, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar agendamentos: {e}")

# Lista de horários disponíveis
horarios = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]
servicos = {
    "Tradicional": 15,
    "Social": 18,
    "Degradê": 23,
    "Navalhado": 25,
    "Pezim": 5,
    "Barba": 15,
}

# Carregar os agendamentos do JSON
agendamentos = carregar_agendamentos()

class BarbeariaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Agendamento - Barbearia Lucas Borges")
        self.root.geometry("400x500")
        self.root.configure(bg="#121212")
        
        tk.Label(root, text="Barbearia Lucas Borges", fg="white", bg="#121212", font=("Arial", 16, "bold")).pack(pady=10)
        
        tk.Label(root, text="Nome:", fg="white", bg="#121212").pack()
        self.nome = tk.Entry(root)
        self.nome.pack()

        tk.Label(root, text="Telefone:", fg="white", bg="#121212").pack()
        self.telefone = tk.Entry(root)
        self.telefone.pack()
        
        tk.Label(root, text="Data (DD/MM/AAAA):", fg="white", bg="#121212").pack()
        self.data_selecionada = tk.Entry(root)
        self.data_selecionada.insert(0, datetime.today().strftime("%d/%m/%Y"))
        self.data_selecionada.pack()
        
        tk.Label(root, text="Horário:", fg="white", bg="#121212").pack()
        self.horario_var = tk.StringVar(root)
        self.horario_var.set(horarios[0])
        self.horario_menu = tk.OptionMenu(root, self.horario_var, *horarios)
        self.horario_menu.pack()

        tk.Label(root, text="Serviços:", fg="white", bg="#121212").pack()
        self.servico_vars = {}
        for servico in servicos:
            var = tk.IntVar()
            chk = tk.Checkbutton(root, text=f"{servico} - R$ {servicos[servico]}", variable=var, fg="white", bg="#121212", selectcolor="#333333")
            chk.pack()
            self.servico_vars[servico] = var
        
        tk.Button(root, text="Confirmar Agendamento", command=self.confirmar_agendamento, bg="#008000", fg="white").pack(pady=10)
        tk.Button(root, text="Cancelar Agendamento", command=self.cancelar_agendamento, bg="#FF0000", fg="white").pack(pady=5)
    
    def confirmar_agendamento(self):
        nome = self.nome.get()
        telefone = self.telefone.get()
        data = self.data_selecionada.get()
        horario = self.horario_var.get()
        servicos_escolhidos = [s for s, var in self.servico_vars.items() if var.get() == 1]
        
        if not nome or not telefone:
            messagebox.showerror("Erro", "Por favor, preencha todos os campos obrigatórios (nome e telefone).")
            return

        if len(servicos_escolhidos) == 0:
            messagebox.showerror("Erro", "Você deve escolher pelo menos 1 serviço.")
            return

        if len(servicos_escolhidos) > 2:
            messagebox.showerror("Erro", "Você pode escolher no máximo 2 serviços.")
            return
        
        if (data, horario) in agendamentos:
            messagebox.showerror("Erro", "Este horário já está ocupado.")
            return
        
        resumo = f"Nome: {nome}\nTelefone: {telefone}\nData: {data}\nHorário: {horario}\nServiços: {', '.join(servicos_escolhidos)}"
        confirmar = messagebox.askyesno("Confirmação", f"Confirma este agendamento?\n\n{resumo}")
        
        if confirmar:
            agendamentos[(data, horario)] = (nome, telefone, servicos_escolhidos)
            salvar_agendamentos(agendamentos)  # Salvar após confirmação
            self.enviar_email("Agendamento Confirmado", resumo)
            messagebox.showinfo("Sucesso", "Agendamento realizado com sucesso!")
    
    def cancelar_agendamento(self):
        data = self.data_selecionada.get()
        horario = self.horario_var.get()
        nome = self.nome.get()
        telefone = self.telefone.get()
        
        if not nome or not telefone:
            messagebox.showerror("Erro", "Nome e telefone são obrigatórios para cancelar um agendamento.")
            return

        if (data, horario) not in agendamentos:
            messagebox.showerror("Erro", "Não há agendamentos neste horário.")
            return

        if agendamentos[(data, horario)][:2] != (nome, telefone):
            messagebox.showerror("Erro", "Nome ou telefone não correspondem ao agendamento.")
            return

        del agendamentos[(data, horario)]
        salvar_agendamentos(agendamentos)  # Salvar após cancelamento
        self.enviar_email("Agendamento Cancelado", f"O agendamento para {data} às {horario} foi cancelado.")
        messagebox.showinfo("Cancelado", "Agendamento cancelado com sucesso!")
    
    def enviar_email(self, assunto, mensagem):
        try:
            msg = MIMEText(mensagem)
            msg['Subject'] = assunto
            msg['From'] = EMAIL
            msg['To'] = EMAIL
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL, SENHA)
            server.sendmail(EMAIL, EMAIL, msg.as_string())
            server.quit()
        except Exception as e:
            messagebox.showerror("Erro de E-mail", f"Falha ao enviar e-mail: {str(e)}")

root = tk.Tk()
app = BarbeariaApp(root)
root.mainloop()

