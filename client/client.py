from socket import *
import sys
import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from datetime import datetime

IPServidor = "localhost"
puertoServidor = 9096

# Se declara e inicializa el socket del cliente
try:
    socketCliente = socket(AF_INET, SOCK_STREAM)
    socketCliente.connect((IPServidor, puertoServidor))
    print(f"Conectado al servidor {IPServidor}:{puertoServidor}")
except ConnectionRefusedError:
    print("Error: No se pudo conectar al servidor. Asegúrate de que está encendido.")
    sys.exit()

usuario_interno = None
usuario_externo = None

def recibir_mensajes():
    """Función que se ejecuta en un hilo separado para recibir mensajes del servidor."""
    while True:
        try:
            respuesta = socketCliente.recv(4096).decode()
            print("respuesta: ", respuesta)

            if not respuesta:
                print("El servidor cerró la conexión.")
                socketCliente.close()
                break
            chat_text.config(state=tk.NORMAL)
            fecha_creacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            chat_text.insert(tk.END, f"({usuario_externo if usuario_externo else socketCliente.getsockname()} - {fecha_creacion}): {respuesta}\n")
            chat_text.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Error al recibir mensaje: {e}")
            socketCliente.close()
            break

def abrir_ventana_registro():
    """Abre una nueva ventana para el registro de usuarios."""
    ventana_registro = tk.Toplevel(root)
    ventana_registro.title("Registro de Usuario")

    tk.Label(ventana_registro, text="Correo:").grid(row=0, column=0, padx=5, pady=5)
    correo_entry = tk.Entry(ventana_registro)
    correo_entry.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(ventana_registro, text="Usuario:").grid(row=1, column=0, padx=5, pady=5)
    usuario_entry = tk.Entry(ventana_registro)
    usuario_entry.grid(row=1, column=1, padx=5, pady=5)

    tk.Label(ventana_registro, text="Contraseña:").grid(row=2, column=0, padx=5, pady=5)
    password_entry = tk.Entry(ventana_registro, show="*")
    password_entry.grid(row=2, column=1, padx=5, pady=5)

    def registrar_usuario():
        global usuario_interno
        correo = correo_entry.get()
        usuario_interno = usuario_entry.get()
        password = password_entry.get()
        if correo and usuario_interno and password:
            registro_info = f"REGISTRO {correo} {usuario_interno} {password}"
            socketCliente.send(registro_info.encode())
            messagebox.showinfo("Registro", "Registro enviado al servidor.")
            ventana_registro.destroy()
        else:
            messagebox.showwarning("Registro", "Todos los campos son obligatorios.")

    boton_registrar = tk.Button(ventana_registro, text="Registrar", command=registrar_usuario)
    boton_registrar.grid(row=3, columnspan=2, pady=10)

def enviar_mensaje():
    mensaje = mensaje_entry.get()
    if mensaje:
        socketCliente.send(mensaje.encode())
        chat_text.config(state=tk.NORMAL)
        fecha_creacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        chat_text.insert(tk.END, f"({usuario_interno if usuario_interno else socketCliente.getsockname()} - {fecha_creacion}): {mensaje}\n")
        chat_text.config(state=tk.DISABLED)
        mensaje_entry.delete(0, tk.END)
        if mensaje.lower() in ['adios', 'bye']:
            socketCliente.close()
            root.quit()

# Configuración de la interfaz gráfica
root = tk.Tk()
root.title("Chatubedo")

chat_text = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD)
chat_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

mensaje_entry = tk.Entry(root)
mensaje_entry.pack(padx=10, pady=5, fill=tk.X, expand=True)

boton_enviar = tk.Button(root, text="Enviar", command=enviar_mensaje)
boton_enviar.pack(padx=10, pady=5, side=tk.LEFT)

boton_registrar = tk.Button(root, text="Registrar", command=abrir_ventana_registro)
boton_registrar.pack(padx=10, pady=5, side=tk.RIGHT)

# Iniciar el hilo que se encargará de recibir mensajes del servidor
hilo_recibir = threading.Thread(target=recibir_mensajes, daemon=True)
hilo_recibir.start()

root.mainloop()