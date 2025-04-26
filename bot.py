import discord
from discord.ext import tasks
from discord import app_commands
import pytz
from datetime import datetime, timedelta
import asyncio
import json
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Intents y configuración inicial
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Obtener el canal y token desde variables de entorno
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # ID del canal como entero
TOKEN = os.getenv("TOKEN")

# Archivo donde se guardarán las mazmorras
DUNGEON_FILE = "dungeons.json"

# Cargar mazmorras desde archivo
if os.path.exists(DUNGEON_FILE):
    with open(DUNGEON_FILE, "r") as f:
        try:
            dungeons = json.load(f)
        except json.JSONDecodeError:
            dungeons = []
else:
    dungeons = [
        {"nombre": "Sukamon", "hora": "15:00", "intervalo": 180},
        {"nombre": "Foresta Area", "hora": "15:05", "intervalo": 90},
    ]
    with open(DUNGEON_FILE, "w") as f:
        json.dump(dungeons, f, indent=2)

# Emojis automáticos según el nombre
dungeon_emojis = {
    "Sukamon": "💩",
    "Foresta Area": "🌳",
    "default": "🕵️"
}

# Guardar cambios al archivo
def guardar_dungeons():
    with open(DUNGEON_FILE, "w") as f:
        json.dump(dungeons, f, indent=2)

# Obtener hora actual en GMT+0 y en Perú
def hora_ahora():
    return datetime.now(pytz.utc)

def hora_peru():
    return datetime.now(pytz.timezone("America/Lima"))

# Calcular próxima hora según hora base y intervalo
def calcular_proxima(hora_base_str, intervalo_min):
    base = datetime.strptime(hora_base_str, "%H:%M").time()
    ahora = hora_ahora().time()
    hoy = hora_ahora().date()
    base_dt = datetime.combine(hoy, base, tzinfo=pytz.utc)

    while base_dt < hora_ahora():
        base_dt += timedelta(minutes=intervalo_min)
    return base_dt

# Crear embed con estilo
def crear_embed(nombre, mensaje, color, hora_peru):
    emoji = dungeon_emojis.get(nombre, dungeon_emojis["default"])
    embed = discord.Embed(
        title=f"{emoji} Mazmorra: {nombre}",
        description=mensaje,
        color=color
    )
    embed.add_field(name="Hora Perú", value=hora_peru.strftime("%H:%M"), inline=True)
    embed.timestamp = datetime.now(pytz.timezone('America/Lima'))
    return embed

# Enviar mensaje con embed
async def enviar_alerta(channel, nombre, minutos_restantes, hora_objetivo):
    ahora = hora_peru()
    if minutos_restantes > 0:
        mensaje = f"⏳ Disponible en {minutos_restantes} minuto{'s' if minutos_restantes > 1 else ''}!"
        color = discord.Color.purple()
    else:
        mensaje = f"⏰ ¡Disponible ahora!"
        color = discord.Color.red()

    embed = crear_embed(nombre, mensaje, color, ahora)
    await channel.send(embed=embed)

# Tarea que revisa las mazmorras cada minuto
@tasks.loop(minutes=1)
async def verificar_mazmorras():
    canal = client.get_channel(CHANNEL_ID)
    if canal is None:
        print("Canal no encontrado. Asegúrate de que el ID sea correcto.")
        return

    for dungeon in dungeons:
        nombre = dungeon["nombre"]
        proxima_hora = calcular_proxima(dungeon["hora"], dungeon["intervalo"])
        diferencia = (proxima_hora - hora_ahora()).total_seconds()
        minutos_restantes = int(diferencia // 60)

        if 0 <= minutos_restantes <= 5:
            await enviar_alerta(canal, nombre, minutos_restantes, proxima_hora.astimezone(pytz.timezone("America/Lima")))

# Slash command para listar las mazmorras
@tree.command(name="mazmorras", description="Lista las mazmorras activas")
async def listar_mazmorras(interaction: discord.Interaction):
    mensaje = "**Mazmorras activas:**\n"
    for d in dungeons:
        mensaje += f"{d['nombre']} - desde las {d['hora']} GMT+0 cada {d['intervalo']} min\n"
    await interaction.response.send_message(mensaje)

# Slash command para modificar una mazmorra
@tree.command(name="modificar", description="Modifica una mazmorra existente")
@app_commands.describe(
    nombre_actual="Nombre actual de la mazmorra",
    campo="Campo a modificar: nombre, hora o intervalo",
    nuevo_valor="Nuevo valor para ese campo"
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
                await interaction.response.send_message("Campo no válido. Usa: nombre, hora o intervalo.")
                return
            guardar_dungeons()
            await interaction.response.send_message(f"Mazmorra '{nombre_actual}' modificada correctamente.")
            return
    await interaction.response.send_message("Mazmorra no encontrada.")

# Slash command para agregar nueva mazmorra
@tree.command(name="agregar", description="Agrega una nueva mazmorra")
@app_commands.describe(
    nombre="Nombre de la nueva mazmorra",
    hora="Hora inicial en formato HH:MM (GMT+0)",
    intervalo="Intervalo en minutos entre cada aparición"
)
async def agregar_mazmorra(interaction: discord.Interaction, nombre: str, hora: str, intervalo: int):
    dungeons.append({"nombre": nombre, "hora": hora, "intervalo": intervalo})
    guardar_dungeons()
    await interaction.response.send_message(f"Mazmorra '{nombre}' agregada correctamente.")

# Slash command para eliminar una mazmorra
@tree.command(name="eliminar", description="Elimina una mazmorra por su nombre")
@app_commands.describe(nombre="Nombre exacto de la mazmorra a eliminar")
async def eliminar_mazmorra(interaction: discord.Interaction, nombre: str):
    global dungeons
    original_count = len(dungeons)
    dungeons = [d for d in dungeons if d["nombre"].lower() != nombre.lower()]
    if len(dungeons) < original_count:
        guardar_dungeons()
        await interaction.response.send_message(f"Mazmorra '{nombre}' eliminada.")
    else:
        await interaction.response.send_message(f"Mazmorra '{nombre}' no encontrada.")

# Slash command para consultar tiempo restante a una mazmorra
@tree.command(name="consultar", description="Consulta cuánto falta para una mazmorra")
@app_commands.describe(nombre="Nombre exacto de la mazmorra a consultar")
async def consultar_mazmorra(interaction: discord.Interaction, nombre: str):
    for d in dungeons:
        if d["nombre"].lower() == nombre.lower():
            proxima_hora = calcular_proxima(d["hora"], d["intervalo"])
            diferencia = (proxima_hora - hora_ahora()).total_seconds()
            minutos_restantes = int(diferencia // 60)
            await interaction.response.send_message(f"⏳ Faltan {minutos_restantes} minutos para '{nombre}'!")
            return
    await interaction.response.send_message("Mazmorra no encontrada.")

# Evento cuando el bot está listo
@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot conectado como {client.user}")
    verificar_mazmorras.start()

# Iniciar bot
client.run(TOKEN)



