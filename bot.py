import discord
from discord.ext import tasks
from discord import app_commands
import pytz
from datetime import datetime, timedelta
import asyncio
import json
import os
from dotenv import load_dotenv
from flask import Flask
import threading

# ==== Configuración inicial ====

# Cargar variables de entorno
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ==== Servidor web para Render ====

app = Flask('')

@app.route('/')
def home():
    return "Bot corriendo"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

# ==== Mazmorras ====

DUNGEON_FILE = "dungeons.json"

# Cargar mazmorras desde archivo o crear por defecto
if os.path.exists(DUNGEON_FILE):
    with open(DUNGEON_FILE, "r") as f:
        try:
            dungeons = json.load(f)
        except json.JSONDecodeError:
            dungeons = []
else:
    dungeons = [
        {"nombre": "Sukamon", "hora": "00:00", "intervalo": 180},
        {"nombre": "Foresta Area", "hora": "00:05", "intervalo": 90},
    ]
    with open(DUNGEON_FILE, "w") as f:
        json.dump(dungeons, f, indent=2)

def guardar_dungeons():
    with open(DUNGEON_FILE, "w") as f:
        json.dump(dungeons, f, indent=2)

# ==== Funciones de tiempo ====

def hora_ahora():
    return datetime.now(pytz.utc)

def hora_peru():
    return datetime.now(pytz.timezone("America/Lima"))

def calcular_proxima(hora_base_str, intervalo_min):
    base = datetime.strptime(hora_base_str, "%H:%M").time()
    hoy = hora_ahora().date()
    base_dt = datetime.combine(hoy, base, tzinfo=pytz.utc)

    while base_dt < hora_ahora():
        base_dt += timedelta(minutes=intervalo_min)
    return base_dt

# ==== Mensajes ====

async def enviar_alerta(channel, nombre, minutos_restantes):
    ahora = hora_peru().strftime("%H:%M")

    if minutos_restantes > 0:
        mensaje = f"⏳ Mazmorra **{nombre}** disponible en {minutos_restantes} minuto(s). (Hora Perú: {ahora})"
    else:
        mensaje = f"⏰ ¡Mazmorra **{nombre}** disponible ahora! (Hora Perú: {ahora})"

    await channel.send(mensaje)

# ==== Tareas programadas ====

@tasks.loop(minutes=1)
async def verificar_mazmorras():
    canal = client.get_channel(CHANNEL_ID)
    if canal is None:
        print("Canal no encontrado. Verifica el CHANNEL_ID.")
        return

    for dungeon in dungeons:
        nombre = dungeon["nombre"]
        proxima_hora = calcular_proxima(dungeon["hora"], dungeon["intervalo"])
        diferencia = (proxima_hora - hora_ahora()).total_seconds()
        minutos_restantes = int(diferencia // 60)

        if 0 <= minutos_restantes <= 5:
            await enviar_alerta(canal, nombre, minutos_restantes)

# ==== Comandos Slash ====

@tree.command(name="mazmorras", description="Lista las mazmorras activas")
async def listar_mazmorras(interaction: discord.Interaction):
    mensaje = "**Mazmorras activas:**\n"
    for d in dungeons:
        mensaje += f"- {d['nombre']}: desde {d['hora']} GMT+0 cada {d['intervalo']} minutos\n"
    await interaction.response.send_message(mensaje)

@tree.command(name="modificar", description="Modifica una mazmorra existente")
@app_commands.describe(
    nombre_actual="Nombre actual",
    campo="Campo a modificar: nombre, hora o intervalo",
    nuevo_valor="Nuevo valor"
)
async def modificar_mazmorra(interaction: discord.Interaction, nombre_actual: str, campo: str, nuevo_valor: str):
    for d in dungeons:
        if d["nombre"].lower() == nombre_actual.lower():
            if campo == "nombre":
                d["nombre"] = nuevo_valor
            elif campo == "hora":
                d["hora"] = nuevo_valor
            elif campo == "intervalo":
                d["intervalo"] = int(nuevo_valor)
            else:
                await interaction.response.send_message("Campo inválido. Usa: nombre, hora o intervalo.")
                return
            guardar_dungeons()
            await interaction.response.send_message(f"Mazmorra '{nombre_actual}' modificada.")
            return
    await interaction.response.send_message("Mazmorra no encontrada.")

@tree.command(name="agregar", description="Agrega una nueva mazmorra")
@app_commands.describe(
    nombre="Nombre de la mazmorra",
    hora="Hora inicial HH:MM GMT+0",
    intervalo="Intervalo en minutos"
)
async def agregar_mazmorra(interaction: discord.Interaction, nombre: str, hora: str, intervalo: int):
    dungeons.append({"nombre": nombre, "hora": hora, "intervalo": intervalo})
    guardar_dungeons()
    await interaction.response.send_message(f"Mazmorra '{nombre}' agregada.")

@tree.command(name="eliminar", description="Elimina una mazmorra existente")
@app_commands.describe(nombre="Nombre exacto")
async def eliminar_mazmorra(interaction: discord.Interaction, nombre: str):
    global dungeons
    original_count = len(dungeons)
    dungeons = [d for d in dungeons if d["nombre"].lower() != nombre.lower()]
    if len(dungeons) < original_count:
        guardar_dungeons()
        await interaction.response.send_message(f"Mazmorra '{nombre}' eliminada.")
    else:
        await interaction.response.send_message(f"Mazmorra '{nombre}' no encontrada.")

@tree.command(name="consultar", description="Consulta el tiempo para una mazmorra")
@app_commands.describe(nombre="Nombre exacto")
async def consultar_mazmorra(interaction: discord.Interaction, nombre: str):
    for d in dungeons:
        if d["nombre"].lower() == nombre.lower():
            proxima_hora = calcular_proxima(d["hora"], d["intervalo"])
            diferencia = (proxima_hora - hora_ahora()).total_seconds()
            minutos_restantes = int(diferencia // 60)
            await interaction.response.send_message(f"Faltan {minutos_restantes} minutos para '{nombre}'.")
            return
    await interaction.response.send_message("Mazmorra no encontrada.")

# ==== Eventos ====

@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot conectado como {client.user}")
    verificar_mazmorras.start()

# ==== Inicio ====

keep_alive()   # <-- Mantiene el servidor web vivo para Render
client.run(TOKEN)





