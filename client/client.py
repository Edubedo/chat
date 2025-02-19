from socket import *
import sys
import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox

IPServidor = "localhost"
puertoServidor = 9096
# IPServidor = "148.213.116.151"
# puertoServidor = 8000

# Se declara e inicializa el socket del cliente
try:
    socketCliente = socket(AF_INET, SOCK_STREAM)
    socketCliente.connect((IPServidor, puertoServidor))
    print(f"Conectado al servidor {IPServidor}:{puertoServidor}")
except ConnectionRefusedError:
    print("Error: No se pudo conectar al servidor. Asegúrate de que está encendido.")
    sys.exit()

def recibir_mensajes():
    """Función que se ejecuta en un hilo separado para recibir mensajes del servidor."""
    while True:
        try:
            respuesta = socketCliente.recv(4096).decode()
            if not respuesta:
                print("El servidor cerró la conexión.")
                socketCliente.close()
                break
            chat_text.config(state=tk.NORMAL)
            chat_text.insert(tk.END, f"{respuesta}\n")
            chat_text.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Error al recibir mensaje: {e}")
            socketCliente.close()
            break

def enviar_archivo(nombre_archivo):
    """Envía una solicitud para enviar un archivo al servidor y espera confirmación."""
    if not os.path.exists(nombre_archivo):
        messagebox.showerror("Error", "El archivo no existe.")
        return

    # Solicitar permiso para enviar el archivo
    socketCliente.send(f"ENVIAR_ARCHIVO {nombre_archivo}".encode())

    # Esperar respuesta del servidor
    respuesta = socketCliente.recv(4096).decode()

    if respuesta == "ACEPTADO":
        with open(nombre_archivo, "rb") as archivo:
            while True:
                datos = archivo.read(4096)
                if not datos:
                    break
                socketCliente.send(datos)
        socketCliente.send(b"FIN_ARCHIVO")
        messagebox.showinfo("Éxito", f"Archivo {nombre_archivo} enviado correctamente.")
    else:
        messagebox.showerror("Error", f"El servidor rechazó el archivo {nombre_archivo}.")

def enviar_mensaje():
    mensaje = mensaje_entry.get()
    if mensaje:
        socketCliente.send(mensaje.encode())
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"Tú: {mensaje}\n")
        chat_text.config(state=tk.DISABLED)
        mensaje_entry.delete(0, tk.END)
        if mensaje.lower() in ['adios', 'bye']:
            socketCliente.close()
            root.quit()

def seleccionar_archivo():
    nombre_archivo = filedialog.askopenfilename()
    if nombre_archivo:
        enviar_archivo(nombre_archivo)

# Configuración de la interfaz gráfica
root = tk.Tk()
root.title("Cliente de Chat")

chat_text = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD)
chat_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

mensaje_entry = tk.Entry(root)
mensaje_entry.pack(padx=10, pady=5, fill=tk.X, expand=True)

boton_enviar = tk.Button(root, text="Enviar", command=enviar_mensaje)
boton_enviar.pack(padx=10, pady=5, side=tk.LEFT)

boton_archivo = tk.Button(root, text="Enviar Archivo", command=seleccionar_archivo)
boton_archivo.pack(padx=10, pady=5, side=tk.RIGHT)

# Iniciar el hilo que se encargará de recibir mensajes del servidor
hilo_recibir = threading.Thread(target=recibir_mensajes, daemon=True)
hilo_recibir.start()

root.mainloop()