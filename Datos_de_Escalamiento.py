import customtkinter as ctk
from tkinter import messagebox
import json
import os
import re

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def encontrar_config(nombre_archivo="config.json"):
    """Busca config.json en la carpeta del script, en la terminal, 
    en subcarpetas y hasta 2 niveles hacia arriba (carpetas padre)."""
    # 1. Carpeta exacta del script y carpeta actual de la terminal
    rutas_directas = [
        os.path.join(BASE_DIR, nombre_archivo),
        os.path.join(os.getcwd(), nombre_archivo),
        os.path.join(os.path.dirname(BASE_DIR), nombre_archivo),
        os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), nombre_archivo),
    ]
    for ruta in rutas_directas:
        if os.path.exists(ruta):
            return os.path.abspath(ruta)

    # 2. Buscar en subcarpetas partiendo del script y de la carpeta padre
    directorios_busqueda = [BASE_DIR, os.getcwd(), os.path.dirname(BASE_DIR)]
    for directorio_base in directorios_busqueda:
        for raiz, directorios, archivos in os.walk(directorio_base):
            if nombre_archivo in archivos:
                return os.path.abspath(os.path.join(raiz, nombre_archivo))

    # Si no existe en ningún lado, devuelve la ruta junto al script para el aviso
    return os.path.join(BASE_DIR, nombre_archivo)


JSON_PATH = encontrar_config("config.json")

ALIAS_PUESTO = ["puesto", "cargo", "rol", "posicion", "posición"]

CATEGORIAS_ORDEN = ["Líder del Proyecto", "Arquitecto", "Desarrollador", "Analista de Código"]

# ---- Validaciones ----
REGEX_TELEFONO = re.compile(r"^\d{10}$")
REGEX_EMAIL_COPPEL = re.compile(r"^[^@\s]+@coppel\.com$", re.IGNORECASE)


# ---------------------------------------------------------
# Funciones de datos (JSON)
# ---------------------------------------------------------
def cargar_datos(path):
    """Carga el JSON externo, agrega únicamente la descripción de datosescalamiento 
    al archivo si no existe y prepara la estructura en memoria para la app."""
    if not os.path.exists(path):
        mensaje = f"No se encontró el archivo 'config.json' en:\n{path}"
        print(f"Advertencia: {mensaje}")
        messagebox.showwarning("Archivo no encontrado", mensaje)
        return {"personas": [], "equipos": {}, "analista_email": None}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # --- Agregar ÚNICAMENTE la descripción al archivo JSON ---
        descripcion = data.setdefault("Descripcion", {})
        nueva_descripcion = "datosescalamiento"

        if nueva_descripcion not in descripcion:
            descripcion[nueva_descripcion] = "Aplicacion para obtener la información de personas y equipos."
            with open(path, "w", encoding="utf-8") as fw:
                json.dump(data, fw, ensure_ascii=False, indent=2)

        # Valores en memoria para que la interfaz funcione sin escribirlos al archivo de inicio
        data.setdefault("personas", [])
        data.setdefault("equipos", {})
        data.setdefault("analista_email", None)
        return data

    except Exception as e:
        messagebox.showerror("Error al cargar JSON", f"No se pudo leer el archivo:\n{e}")
        return {"personas": [], "equipos": {}, "analista_email": None}


def guardar_datos(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Error al guardar configuración", f"No se pudo guardar:\n{e}")


def obtener_puesto(persona):
    for clave in ALIAS_PUESTO:
        if clave in persona and persona[clave]:
            return persona[clave]
    return "Sin puesto"


def clasificar_puesto(puesto):
    """Clasifica el puesto en una de las categorías fijas (o 'Otros')."""
    p = (puesto or "").lower()
    if "líder" in p or "lider" in p:
        return "Líder del Proyecto"
    if "arquitect" in p:
        return "Arquitecto"
    if "desarroll" in p:
        return "Desarrollador"
    if "analista" in p:
        return "Analista de Código"
    return "Otros"


def orden_categoria_key(persona):
    """Devuelve la posición numérica de la categoría del puesto, para poder ordenar."""
    categoria = clasificar_puesto(obtener_puesto(persona))
    if categoria in CATEGORIAS_ORDEN:
        return CATEGORIAS_ORDEN.index(categoria)
    return len(CATEGORIAS_ORDEN)  # "Otros" siempre al final


def ordenar_por_categoria(personas):
    """Ordena una lista de personas respetando el orden de CATEGORIAS_ORDEN."""
    return sorted(personas, key=orden_categoria_key)


def deduplicar_personas(personas):
    """Se usa SOLO internamente (ej. elegir el registro por defecto de un equipo o
    para listas de selección de analistas), NO para las vistas de resultados,
    ya que ahí sí queremos ver cada rol de la persona por separado."""
    mejores = {}
    sin_email_contador = 0
    for p in personas:
        email = p.get("email")
        if not email:
            sin_email_contador -= 1
            mejores[sin_email_contador] = p
            continue
        actual = mejores.get(email)
        if actual is None or orden_categoria_key(p) < orden_categoria_key(actual):
            mejores[email] = p
    return list(mejores.values())


def persona_key(p):
    """Clave única por registro: email + puesto exacto (permite distinguir
    dos registros de la misma persona con distinto rol)."""
    return (p.get("email", ""), obtener_puesto(p))


def extraer_email(entry):
    """Un integrante de equipo puede ser un string (email) o un dict {'email':..., 'puesto':...}."""
    if isinstance(entry, dict):
        return entry.get("email")
    return entry


def extraer_puesto_override(entry):
    """Si el integrante es un dict, devuelve el puesto forzado (o None si es solo un string)."""
    if isinstance(entry, dict):
        return entry.get("puesto")
    return None


def obtener_equipo_analistas_emails(data):
    """Busca en 'equipos' el que corresponda a Analistas de Código."""
    equipos = data.get("equipos", {})
    for nombre, integrantes in equipos.items():
        if "analista" in nombre.lower():
            return [extraer_email(e) for e in integrantes]
    return None


def obtener_personas_analistas(data):
    """Devuelve la lista de personas (una por email) que son Analistas de Código."""
    correos = obtener_equipo_analistas_emails(data)
    personas = data.get("personas", [])

    if correos:
        resultado = [p for p in personas if p.get("email") in correos
                     and clasificar_puesto(obtener_puesto(p)) == "Analista de Código"]
        if resultado:
            return deduplicar_personas(resultado)

    return deduplicar_personas(
        [p for p in personas if clasificar_puesto(obtener_puesto(p)) == "Analista de Código"]
    )


def agrupar_personas_por_email(personas):
    """Agrupa registros por email, cada grupo ordenado por prioridad de categoría."""
    agrupado = {}
    for p in personas:
        email = p.get("email")
        if not email:
            continue
        agrupado.setdefault(email, []).append(p)
    for email in agrupado:
        agrupado[email].sort(key=orden_categoria_key)
    return agrupado


def validar_telefono(telefono):
    """Debe tener exactamente 10 dígitos numéricos."""
    return bool(REGEX_TELEFONO.match(telefono.strip()))


def validar_email_coppel(email):
    """Debe tener formato de correo válido y terminar en @coppel.com."""
    return bool(REGEX_EMAIL_COPPEL.match(email.strip()))


def resolver_integrante(entry, personas_data):
    """Dado un integrante de equipo (string o dict con override), devuelve el
    registro de persona resuelto (respetando el rol forzado) o None si no existe."""
    email = extraer_email(entry)
    puesto_override = extraer_puesto_override(entry)

    candidatos = [p for p in personas_data if p.get("email") == email]
    if not candidatos:
        return None

    if puesto_override:
        elegido = next((p for p in candidatos
                         if obtener_puesto(p).lower() == puesto_override.lower()), None)
        if not elegido:
            elegido = next((p for p in candidatos
                             if clasificar_puesto(obtener_puesto(p)) == clasificar_puesto(puesto_override)), None)
        if not elegido:
            elegido = candidatos[0]
        return elegido

    return deduplicar_personas(candidatos)[0]


def obtener_lider_de_equipo(integrantes, personas_data):
    """Busca dentro de los integrantes del equipo a la persona que sea Líder del Proyecto."""
    for entry in integrantes:
        persona = resolver_integrante(entry, personas_data)
        if persona and clasificar_puesto(obtener_puesto(persona)) == "Líder del Proyecto":
            return persona
    return None


def coincide_busqueda(persona, texto_busqueda):
    """Revisa si el texto buscado aparece en nombre, teléfono, puesto o email (sin importar mayúsculas)."""
    texto = texto_busqueda.strip().lower()
    if not texto:
        return False

    campos = [
        persona.get("nombre", ""),
        persona.get("telefono", ""),
        obtener_puesto(persona),
        persona.get("email", ""),
    ]
    return any(texto in str(campo).lower() for campo in campos)


# ---------------------------------------------------------
# DIÁLOGO: Crear / Editar Persona
# ---------------------------------------------------------
class PersonaDialog(ctk.CTkToplevel):
    def __init__(self, master, on_guardar, persona=None):
        super().__init__(master)
        self.title("Nueva Persona" if persona is None else "Editar Persona")
        self.geometry("380x420")
        self.resizable(False, False)
        self.on_guardar = on_guardar
        self.persona_original = persona
        self.transient(master)
        self.grab_set()

        # Validador para que el campo de teléfono solo acepte dígitos (máx. 10)
        vcmd = (self.register(self._validar_input_telefono), "%P")

        ctk.CTkLabel(self, text="Nombre completo:").pack(anchor="w", padx=20, pady=(20, 0))
        self.entry_nombre = ctk.CTkEntry(self, width=330)
        self.entry_nombre.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Puesto:").pack(anchor="w", padx=20)
        self.combo_puesto = ctk.CTkComboBox(
            self, width=330,
            values=["Líder de Proyecto", "Arquitecto", "Desarrollador", "Analista de Código"])
        self.combo_puesto.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Teléfono (10 dígitos):").pack(anchor="w", padx=20)
        self.entry_telefono = ctk.CTkEntry(self, width=330, validate="key", validatecommand=vcmd)
        self.entry_telefono.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Email (@coppel.com):").pack(anchor="w", padx=20)
        self.entry_email = ctk.CTkEntry(self, width=330, placeholder_text="usuario@coppel.com")
        self.entry_email.pack(padx=20, pady=(0, 5))

        if persona:
            self.entry_nombre.insert(0, persona.get("nombre", ""))
            self.combo_puesto.set(obtener_puesto(persona))
            self.entry_telefono.insert(0, persona.get("telefono", ""))
            self.entry_email.insert(0, persona.get("email", ""))
            self.entry_email.configure(state="disabled")
            ctk.CTkLabel(self, text="✎ El email no se puede editar (usa Eliminar + Nueva Persona si cambia).",
                         text_color="gray", font=ctk.CTkFont(size=10), wraplength=320).pack(padx=20)
        else:
            self.combo_puesto.set("Desarrollador")

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=15)
        ctk.CTkButton(botones, text="Guardar", command=self._guardar).pack(side="left", padx=10)
        ctk.CTkButton(botones, text="Cancelar", fg_color="#2b2b2b", hover_color="#3a3a3a",
                      command=self.destroy).pack(side="left", padx=10)

    def _validar_input_telefono(self, texto_propuesto):
        """Solo permite dígitos y un máximo de 10 caracteres mientras se escribe."""
        if texto_propuesto == "":
            return True
        return texto_propuesto.isdigit() and len(texto_propuesto) <= 10

    def _guardar(self):
        nombre = self.entry_nombre.get().strip()
        puesto = self.combo_puesto.get().strip()
        telefono = self.entry_telefono.get().strip()
        email = self.entry_email.get().strip()

        if not nombre or not puesto or not telefono or not email:
            messagebox.showwarning("Datos incompletos", "Todos los campos son obligatorios.")
            return

        if not validar_telefono(telefono):
            messagebox.showwarning("Teléfono inválido", "El teléfono debe tener exactamente 10 dígitos numéricos.")
            return

        if not validar_email_coppel(email):
            messagebox.showwarning("Correo inválido", "El correo debe tener el formato usuario@coppel.com")
            return

        nueva_persona = {"nombre": nombre, "puesto": puesto, "telefono": telefono, "email": email}
        self.on_guardar(nueva_persona, self.persona_original)
        self.destroy()


# ---------------------------------------------------------
# DIÁLOGO: Crear / Editar Equipo
# ---------------------------------------------------------
class EquipoDialog(ctk.CTkToplevel):
    def __init__(self, master, personas, on_guardar, nombre_equipo=None, integrantes=None):
        super().__init__(master)
        self.title("Nuevo Equipo" if nombre_equipo is None else f"Editar: {nombre_equipo}")
        self.geometry("500x600")
        self.on_guardar = on_guardar
        self.nombre_original = nombre_equipo
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text="Nombre del equipo:").pack(anchor="w", padx=20, pady=(20, 0))
        self.entry_nombre = ctk.CTkEntry(self, width=450)
        self.entry_nombre.pack(padx=20, pady=(0, 10))
        if nombre_equipo:
            self.entry_nombre.insert(0, nombre_equipo)

        ctk.CTkLabel(self, text="Selecciona integrantes y el rol que tendrán en este equipo:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=20, pady=(10, 5))

        self.scroll = ctk.CTkScrollableFrame(self, width=460, height=400)
        self.scroll.pack(padx=20, pady=(0, 10), fill="both", expand=True)
        self.scroll.grid_columnconfigure(1, weight=1)

        agrupado = agrupar_personas_por_email(personas)

        actuales = {}
        if integrantes:
            for entry in integrantes:
                email = extraer_email(entry)
                puesto_ov = extraer_puesto_override(entry)
                actuales[email] = puesto_ov  # puede ser None (usa el rol por defecto)

        self.checks = {}
        self.combos = {}

        fila = 0
        for email, registros in sorted(agrupado.items(), key=lambda kv: kv[1][0].get("nombre", "")):
            nombre = registros[0].get("nombre", "Sin nombre")
            puestos_disponibles = [obtener_puesto(r) for r in registros]

            marcado = email in actuales
            var = ctk.BooleanVar(value=marcado)
            self.checks[email] = var

            fila_frame = ctk.CTkFrame(self.scroll, fg_color="#111318", corner_radius=8)
            fila_frame.grid(row=fila, column=0, columnspan=3, sticky="ew", padx=4, pady=3)
            fila_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkCheckBox(fila_frame, text="", variable=var, width=20).grid(row=0, column=0, padx=(8, 4), pady=6)
            ctk.CTkLabel(fila_frame, text=f"{nombre}\n{email}", anchor="w",
                         justify="left").grid(row=0, column=1, sticky="ew", pady=4)

            combo = ctk.CTkComboBox(fila_frame, values=puestos_disponibles, width=170)
            if marcado and actuales[email]:
                combo.set(actuales[email])
            else:
                combo.set(puestos_disponibles[0])
            combo.grid(row=0, column=2, padx=8, pady=6)
            self.combos[email] = combo

            fila += 1

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=10)
        ctk.CTkButton(botones, text="Guardar", command=self._guardar).pack(side="left", padx=10)
        ctk.CTkButton(botones, text="Cancelar", fg_color="#2b2b2b", hover_color="#3a3a3a",
                      command=self.destroy).pack(side="left", padx=10)

    def _guardar(self):
        nombre = self.entry_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Falta el nombre", "Escribe un nombre para el equipo.")
            return

        integrantes = []
        for email, var in self.checks.items():
            if not var.get():
                continue
            puesto_elegido = self.combos[email].get()
            valores_disponibles = self.combos[email].cget("values")
            primero = valores_disponibles[0] if valores_disponibles else puesto_elegido

            if puesto_elegido == primero:
                integrantes.append(email)
            else:
                integrantes.append({"email": email, "puesto": puesto_elegido})

        if not integrantes:
            messagebox.showwarning("Sin integrantes", "Selecciona al menos un integrante.")
            return

        self.on_guardar(nombre, integrantes, self.nombre_original)
        self.destroy()


# ---------------------------------------------------------
# APLICACIÓN PRINCIPAL
# ---------------------------------------------------------
class DataApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Datos de Escalamiento - Portal Proveedores")
        self.geometry("1050x760")
        self.minsize(900, 640)

        self.data = cargar_datos(JSON_PATH)
        self.check_vars = {}          # (email, puesto) -> BooleanVar
        self.analista_opciones = {}   # "Nombre (email)" -> email

        self._construir_sidebar()
        self._construir_panel_principal()
        self._refrescar_todo()
        # La terminal queda limpia al abrir la app

    # ---------------------------------------------------------
    # Refrescar todas las vistas de golpe (usado tras crear/editar/eliminar)
    # ---------------------------------------------------------
    def _refrescar_todo(self):
        self._refrescar_lista_personas()
        self._refrescar_equipos()
        self._refrescar_selector_analista()
        if hasattr(self, "admin_personas_frame"):
            self._refrescar_admin_personas()
        if hasattr(self, "admin_equipos_frame"):
            self._refrescar_admin_equipos()

    # ---------------------------------------------------------
    # SIDEBAR
    # ---------------------------------------------------------
    def _construir_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#111318")
        sidebar.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(sidebar, text="📊", font=ctk.CTkFont(size=32)).grid(row=0, column=0, pady=(30, 0))
        ctk.CTkLabel(sidebar, text="Datos de Escalamiento", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="#3B8ED0").grid(row=1, column=0, pady=(0, 20))

        ctk.CTkLabel(sidebar, text="ARCHIVO DE DATOS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray").grid(row=2, column=0, sticky="w", padx=20)

        ctk.CTkLabel(sidebar, text="⭐ ANALISTA DE CÓDIGO", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray").grid(row=4, column=0, sticky="w", padx=20)

        self.lbl_analista_actual = ctk.CTkLabel(
            sidebar, text="No asignado", text_color="#3B8ED0",
            wraplength=200, justify="left", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_analista_actual.grid(row=5, column=0, sticky="w", padx=20, pady=(5, 8))

        self.combo_analista = ctk.CTkComboBox(sidebar, values=["(sin analistas)"], width=200)
        self.combo_analista.grid(row=6, column=0, padx=20, pady=(0, 8))

        ctk.CTkButton(sidebar, text="✅ Establecer como predeterminado", width=200,
                      command=self._establecer_analista_desde_combo).grid(row=7, column=0, padx=20, pady=(0, 5))
        ctk.CTkButton(sidebar, text="✖ Quitar predeterminado", width=200, fg_color="#2b2b2b",
                      hover_color="#3a3a3a", command=self._quitar_analista).grid(row=8, column=0, padx=20, pady=(0, 10))

        ctk.CTkButton(sidebar, text="Salir", fg_color="#2b2b2b", hover_color="#3a3a3a",
                      command=self.destroy).grid(row=10, column=0, pady=20, padx=20, sticky="s")

    def _refrescar_selector_analista(self):
        self.analista_opciones = {}
        etiquetas = []

        analistas = obtener_personas_analistas(self.data)
        for p in analistas:
            nombre = p.get("nombre", "Sin nombre")
            email = p.get("email", "")
            etiqueta = f"{nombre} ({email})"
            self.analista_opciones[etiqueta] = email
            etiquetas.append(etiqueta)

        if not etiquetas:
            etiquetas = ["(sin analistas definidos)"]

        self.combo_analista.configure(values=etiquetas)

        email_actual = self.data.get("analista_email")
        etiqueta_actual = next((k for k, v in self.analista_opciones.items() if v == email_actual), None)
        if etiqueta_actual:
            self.combo_analista.set(etiqueta_actual)
        else:
            self.combo_analista.set(etiquetas[0])

        self._actualizar_label_analista()

    def _establecer_analista_desde_combo(self):
        etiqueta = self.combo_analista.get()
        email = self.analista_opciones.get(etiqueta)
        if not email:
            self._log("⚠ Selecciona un Analista de Código válido del listado.")
            return
        self.data["analista_email"] = email
        guardar_datos(JSON_PATH, self.data)
        self._actualizar_label_analista()
        self._refrescar_lista_personas()
        self._log(f"⭐ Analista de código predeterminado actualizado: {etiqueta}")

    def _quitar_analista(self):
        self.data["analista_email"] = None
        guardar_datos(JSON_PATH, self.data)
        self._actualizar_label_analista()
        self._refrescar_lista_personas()
        self._log("✖ Se quitó el analista de código predeterminado.")

    def _actualizar_label_analista(self):
        persona = self._buscar_analista_predeterminado()
        if persona:
            self.lbl_analista_actual.configure(text=persona.get("nombre", persona.get("email")))
        else:
            self.lbl_analista_actual.configure(text="No asignado")

    def _buscar_persona_por_email(self, email):
        if not email:
            return None
        candidatos = [p for p in self.data.get("personas", []) if p.get("email") == email]
        if not candidatos:
            return None
        return deduplicar_personas(candidatos)[0]

    def _buscar_analista_predeterminado(self):
        """Busca específicamente el registro con puesto 'Analista de Código' para el email guardado."""
        email = self.data.get("analista_email")
        if not email:
            return None
        personas = self.data.get("personas", [])
        candidato = next((p for p in personas if p.get("email") == email
                           and clasificar_puesto(obtener_puesto(p)) == "Analista de Código"), None)
        if candidato:
            return candidato
        return self._buscar_persona_por_email(email)

    # ---------------------------------------------------------
    # PANEL PRINCIPAL
    # ---------------------------------------------------------
    def _construir_panel_principal(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(main)
        self.tabview.grid(row=0, column=0, sticky="nsew", pady=(0, 15))
        self.tabview.add("Personas")
        self.tabview.add("Equipos")
        self.tabview.add("Buscar")
        self.tabview.add("Gestionar")

        self._construir_tab_personas(self.tabview.tab("Personas"))
        self._construir_tab_equipos(self.tabview.tab("Equipos"))
        self._construir_tab_buscar(self.tabview.tab("Buscar"))
        self._construir_tab_gestionar(self.tabview.tab("Gestionar"))

        self._construir_terminal(main)

    # ---------------- TAB PERSONAS ----------------
    def _construir_tab_personas(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(5, 10))
        top.grid_columnconfigure(0, weight=1)

        self.entry_filtro = ctk.CTkEntry(top, placeholder_text="🔍 Filtrar por nombre o correo...")
        self.entry_filtro.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry_filtro.bind("<KeyRelease>", lambda e: self._refrescar_lista_personas())

        ctk.CTkButton(top, text="Buscar correo exacto", width=150,
                      command=self._buscar_correo_exacto).grid(row=0, column=1)

        botones = ctk.CTkFrame(tab, fg_color="transparent")
        botones.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkButton(botones, text="Seleccionar todos", width=140,
                      command=self._seleccionar_todos).pack(side="left", padx=(0, 10))
        ctk.CTkButton(botones, text="Limpiar selección", width=140, fg_color="#2b2b2b",
                      hover_color="#3a3a3a", command=self._limpiar_seleccion).pack(side="left", padx=(0, 10))
        ctk.CTkButton(botones, text="⚡ Mostrar seleccionados", fg_color="#2fa572",
                      command=self._mostrar_seleccionados).pack(side="left")

        self.lista_personas_frame = ctk.CTkScrollableFrame(tab, fg_color="#1a1d24")
        self.lista_personas_frame.grid(row=2, column=0, sticky="nsew")
        self.lista_personas_frame.grid_columnconfigure(0, weight=1)

    def _refrescar_lista_personas(self):
        for w in self.lista_personas_frame.winfo_children():
            w.destroy()

        filtro = self.entry_filtro.get().strip().lower() if hasattr(self, "entry_filtro") else ""
        personas = self.data.get("personas", [])

        if filtro:
            personas = [p for p in personas
                        if filtro in p.get("nombre", "").lower() or filtro in p.get("email", "").lower()]

        # SIN deduplicar: si una persona tiene varios roles, se muestran todos por separado.
        if not personas:
            ctk.CTkLabel(self.lista_personas_frame, text="No hay personas que coincidan.",
                         text_color="gray").grid(row=0, column=0, sticky="w", padx=10, pady=10)
            return

        grupos = {}
        for p in personas:
            categoria = clasificar_puesto(obtener_puesto(p))
            grupos.setdefault(categoria, []).append(p)

        orden_final = CATEGORIAS_ORDEN + ["Otros"]
        email_analista = self.data.get("analista_email")

        fila_idx = 0
        for categoria in orden_final:
            if categoria not in grupos:
                continue

            ctk.CTkLabel(self.lista_personas_frame, text=f"— {categoria} —",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="#3B8ED0").grid(row=fila_idx, column=0, sticky="w", padx=8, pady=(14, 4))
            fila_idx += 1

            for persona in grupos[categoria]:
                key = persona_key(persona)
                if key not in self.check_vars:
                    self.check_vars[key] = ctk.BooleanVar(value=False)

                fila = ctk.CTkFrame(self.lista_personas_frame, fg_color="#111318", corner_radius=8)
                fila.grid(row=fila_idx, column=0, sticky="ew", padx=8, pady=4)
                fila.grid_columnconfigure(1, weight=1)

                ctk.CTkCheckBox(fila, text="", variable=self.check_vars[key], width=20).grid(
                    row=0, column=0, padx=(10, 5), pady=8)

                marca = " ⭐" if persona.get("email") == email_analista else ""
                texto = f"{persona.get('nombre', 'Sin nombre')}{marca}  —  {persona.get('email', '')}"
                ctk.CTkLabel(fila, text=texto, anchor="w").grid(row=0, column=1, sticky="ew", pady=8)

                if categoria == "Analista de Código":
                    ctk.CTkButton(fila, text="⭐ Predeterminar", width=130, fg_color="#2b2b2b",
                                  hover_color="#3a3a3a",
                                  command=lambda e=persona.get("email"): self._establecer_analista_directo(e)
                                  ).grid(row=0, column=2, padx=10, pady=6)

                fila_idx += 1

    def _establecer_analista_directo(self, email):
        self.data["analista_email"] = email
        guardar_datos(JSON_PATH, self.data)
        self._actualizar_label_analista()
        self._refrescar_selector_analista()
        self._refrescar_lista_personas()
        persona = self._buscar_analista_predeterminado()
        nombre = persona.get("nombre", email) if persona else email
        self._log(f"⭐ Analista de código predeterminado actualizado: {nombre}")

    def _seleccionar_todos(self):
        for p in self.data.get("personas", []):
            key = persona_key(p)
            if key not in self.check_vars:
                self.check_vars[key] = ctk.BooleanVar(value=False)
            self.check_vars[key].set(True)
        self._refrescar_lista_personas()

    def _limpiar_seleccion(self):
        for var in self.check_vars.values():
            var.set(False)
        self._refrescar_lista_personas()

    def _mostrar_seleccionados(self):
        """Combina en una sola lista al Analista de Código predeterminado (si no está
        ya incluido) con las personas seleccionadas (respetando el rol exacto elegido)."""
        personas_data = self.data.get("personas", [])
        seleccionados_keys = [key for key, var in self.check_vars.items() if var.get()]

        personas_resultado = []
        for email, puesto in seleccionados_keys:
            persona = next((p for p in personas_data
                             if p.get("email") == email and obtener_puesto(p) == puesto), None)
            if persona:
                personas_resultado.append(persona)

        emails_incluidos = {p.get("email") for p in personas_resultado}
        analista = self._buscar_analista_predeterminado()
        if analista and analista.get("email") not in emails_incluidos:
            personas_resultado.append(analista)

        if not personas_resultado:
            self._log("⚠ No has seleccionado a nadie y no hay un Analista de Código predeterminado.")
            return

        self._limpiar_terminal()
        self._mostrar_personas(personas_resultado)

    def _buscar_correo_exacto(self):
        email = self.entry_filtro.get().strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            self._log("⚠ Escribe un correo válido en el filtro para buscarlo exacto.")
            return
        personas = [p for p in self.data.get("personas", [])
                    if p.get("email", "").lower() == email.lower()]
        self._limpiar_terminal()
        if personas:
            self._mostrar_personas(personas)
        else:
            self._log(f"❌ No se encontró ningún registro para: {email}")

    # ---------------- TAB EQUIPOS (agrupados por Líder del Proyecto) ----------------
    def _construir_tab_equipos(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="Equipos agrupados por Líder del Proyecto:",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", pady=(5, 10))

        self.equipos_frame = ctk.CTkScrollableFrame(tab, fg_color="#1a1d24")
        self.equipos_frame.grid(row=1, column=0, sticky="nsew")
        self.equipos_frame.grid_columnconfigure((0, 1), weight=1)

    def _refrescar_equipos(self):
        for w in self.equipos_frame.winfo_children():
            w.destroy()

        equipos = self.data.get("equipos", {})
        if not equipos:
            ctk.CTkLabel(self.equipos_frame, text="No hay equipos definidos. Créalos en la pestaña 'Gestionar'.",
                         text_color="gray").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=10)
            return

        personas_data = self.data.get("personas", [])

        # Agrupar equipos según quién sea el Líder del Proyecto dentro de cada uno
        grupos_por_lider = {}
        for nombre_equipo, integrantes in equipos.items():
            lider = obtener_lider_de_equipo(integrantes, personas_data)
            clave_lider = lider.get("nombre") if lider else "Sin líder asignado"
            grupos_por_lider.setdefault(clave_lider, []).append((nombre_equipo, integrantes))

        # Orden: líderes con nombre en orden alfabético, "Sin líder asignado" siempre al final
        lideres_ordenados = sorted(l for l in grupos_por_lider if l != "Sin líder asignado")
        if "Sin líder asignado" in grupos_por_lider:
            lideres_ordenados.append("Sin líder asignado")

        fila_idx = 0
        for lider_nombre in lideres_ordenados:
            equipos_del_lider = grupos_por_lider[lider_nombre]

            titulo = (f"— 👤 Líder: {lider_nombre} —"
                      if lider_nombre != "Sin líder asignado" else "— ⚠ Sin líder asignado —")
            ctk.CTkLabel(self.equipos_frame, text=titulo,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color="#3B8ED0").grid(row=fila_idx, column=0, columnspan=2,
                                                     sticky="w", padx=8, pady=(16, 6))
            fila_idx += 1

            col = 0
            for nombre_equipo, integrantes in equipos_del_lider:
                card = ctk.CTkFrame(self.equipos_frame, fg_color="#111318", corner_radius=10)
                card.grid(row=fila_idx, column=col, padx=8, pady=8, sticky="ew")

                ctk.CTkLabel(card, text=f"👥 {nombre_equipo}",
                             font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(15, 5), padx=15, anchor="w")
                ctk.CTkLabel(card, text=f"{len(integrantes)} integrante(s)",
                             text_color="gray").pack(padx=15, anchor="w")
                ctk.CTkButton(card, text="⚡ Mostrar equipo", width=140,
                              command=lambda n=nombre_equipo, i=integrantes: self._mostrar_equipo(n, i)
                              ).pack(pady=15)

                col += 1
                if col > 1:
                    col = 0
                    fila_idx += 1

            if col != 0:
                fila_idx += 1

    def _mostrar_equipo(self, nombre_equipo, integrantes):
        """Muestra a todo el equipo respetando overrides de puesto por integrante,
        y siempre agrega al Analista de Código predeterminado si no está ya incluido."""
        personas_data = self.data.get("personas", [])

        personas_resultado = []
        faltantes = []

        for entry in integrantes:
            elegido = resolver_integrante(entry, personas_data)
            if elegido is None:
                faltantes.append(extraer_email(entry))
                continue
            personas_resultado.append(elegido)

        emails_ya_incluidos = {p.get("email") for p in personas_resultado}
        analista = self._buscar_analista_predeterminado()
        if analista and analista.get("email") not in emails_ya_incluidos:
            personas_resultado.append(analista)

        self._limpiar_terminal()
        self._mostrar_personas(personas_resultado)
        if faltantes:
            self._log(f"⚠ No se encontraron datos para: {', '.join(faltantes)}")

    # ---------------- TAB BUSCAR (búsqueda libre por cualquier campo) ----------------
    def _construir_tab_buscar(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(tab, text="Escribe nombre, teléfono, puesto o correo:",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", pady=(5, 8))

        fila_busqueda = ctk.CTkFrame(tab, fg_color="transparent")
        fila_busqueda.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        fila_busqueda.grid_columnconfigure(0, weight=1)

        self.entry_buscar = ctk.CTkEntry(
            fila_busqueda,
            placeholder_text="Ej: Nombre, Teléfono, Arquitecto, usuario@coppel.com")
        self.entry_buscar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry_buscar.bind("<Return>", lambda e: self._ejecutar_busqueda_libre())

        ctk.CTkButton(fila_busqueda, text="🔍 Buscar", width=120,
                      command=self._ejecutar_busqueda_libre).grid(row=0, column=1)

    def _ejecutar_busqueda_libre(self):
        texto = self.entry_buscar.get().strip()
        if not texto:
            self._log("⚠ Escribe algo para buscar (nombre, teléfono, puesto o correo).")
            return

        resultados = [p for p in self.data.get("personas", []) if coincide_busqueda(p, texto)]

        self._limpiar_terminal()
        if resultados:
            self._mostrar_personas(resultados)
        else:
            self._log(f"❌ No se encontraron coincidencias para: {texto}")

    # ---------------- TAB GESTIONAR (CRUD) ----------------
    def _construir_tab_gestionar(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        subtabs = ctk.CTkTabview(tab)
        subtabs.grid(row=0, column=0, sticky="nsew")
        subtabs.add("Personas (Escalamiento)")
        subtabs.add("Equipos")

        self._construir_subtab_personas_admin(subtabs.tab("Personas (Escalamiento)"))
        self._construir_subtab_equipos_admin(subtabs.tab("Equipos"))

    # --- Sub-tab: Administrar Personas ---
    def _construir_subtab_personas_admin(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(top, text="➕ Nueva Persona",
                      command=self._abrir_dialogo_nueva_persona).pack(side="left")

        self.admin_personas_frame = ctk.CTkScrollableFrame(tab, fg_color="#1a1d24")
        self.admin_personas_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.admin_personas_frame.grid_columnconfigure(0, weight=1)

        self._refrescar_admin_personas()

    def _refrescar_admin_personas(self):
        for w in self.admin_personas_frame.winfo_children():
            w.destroy()

        personas = self.data.get("personas", [])
        if not personas:
            ctk.CTkLabel(self.admin_personas_frame, text="No hay personas registradas.",
                         text_color="gray").grid(row=0, column=0, sticky="w", padx=10, pady=10)
            return

        personas_ordenadas = ordenar_por_categoria(personas)

        for i, persona in enumerate(personas_ordenadas):
            fila = ctk.CTkFrame(self.admin_personas_frame, fg_color="#111318", corner_radius=8)
            fila.grid(row=i, column=0, sticky="ew", padx=6, pady=4)
            fila.grid_columnconfigure(0, weight=1)

            texto = f"{obtener_puesto(persona)}: {persona.get('nombre', 'Sin nombre')}  —  {persona.get('email', '')}"
            ctk.CTkLabel(fila, text=texto, anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=8)

            ctk.CTkButton(fila, text="✏️ Editar", width=90, fg_color="#2b2b2b", hover_color="#3a3a3a",
                          command=lambda p=persona: self._abrir_dialogo_editar_persona(p)).grid(
                row=0, column=1, padx=5, pady=6)
            ctk.CTkButton(fila, text="🗑️ Eliminar", width=90, fg_color="#a13d3d", hover_color="#c94f4f",
                          command=lambda p=persona: self._eliminar_persona(p)).grid(
                row=0, column=2, padx=(0, 10), pady=6)

    def _abrir_dialogo_nueva_persona(self):
        PersonaDialog(self, on_guardar=self._guardar_persona, persona=None)

    def _abrir_dialogo_editar_persona(self, persona):
        PersonaDialog(self, on_guardar=self._guardar_persona, persona=persona)

    def _guardar_persona(self, nueva_data, original):
        personas = self.data.setdefault("personas", [])
        if original is None:
            personas.append(nueva_data)
        else:
            idx = next((i for i, p in enumerate(personas) if p is original), None)
            if idx is not None:
                personas[idx] = nueva_data
            else:
                personas.append(nueva_data)
        guardar_datos(JSON_PATH, self.data)
        self._refrescar_todo()
        self._log(f"✅ Persona guardada: {obtener_puesto(nueva_data)} - {nueva_data.get('nombre')}")

    def _eliminar_persona(self, persona):
        if not messagebox.askyesno("Confirmar eliminación",
                                    f"¿Eliminar a {persona.get('nombre')} como {obtener_puesto(persona)}?"):
            return
        personas = self.data.get("personas", [])
        idx = next((i for i, p in enumerate(personas) if p is persona), None)
        if idx is not None:
            personas.pop(idx)
            guardar_datos(JSON_PATH, self.data)
            self._refrescar_todo()
            self._log(f"🗑️ Persona eliminada: {persona.get('nombre')}")

    # --- Sub-tab: Administrar Equipos ---
    def _construir_subtab_equipos_admin(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(top, text="➕ Nuevo Equipo",
                      command=self._abrir_dialogo_nuevo_equipo).pack(side="left")

        self.admin_equipos_frame = ctk.CTkScrollableFrame(tab, fg_color="#1a1d24")
        self.admin_equipos_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.admin_equipos_frame.grid_columnconfigure(0, weight=1)

        self._refrescar_admin_equipos()

    def _refrescar_admin_equipos(self):
        for w in self.admin_equipos_frame.winfo_children():
            w.destroy()

        equipos = self.data.get("equipos", {})
        if not equipos:
            ctk.CTkLabel(self.admin_equipos_frame, text="No hay equipos registrados.",
                         text_color="gray").grid(row=0, column=0, sticky="w", padx=10, pady=10)
            return

        for i, (nombre_equipo, integrantes) in enumerate(equipos.items()):
            fila = ctk.CTkFrame(self.admin_equipos_frame, fg_color="#111318", corner_radius=8)
            fila.grid(row=i, column=0, sticky="ew", padx=6, pady=4)
            fila.grid_columnconfigure(0, weight=1)

            texto = f"👥 {nombre_equipo}  —  {len(integrantes)} integrante(s)"
            ctk.CTkLabel(fila, text=texto, anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=8)

            ctk.CTkButton(fila, text="✏️ Editar", width=90, fg_color="#2b2b2b", hover_color="#3a3a3a",
                          command=lambda n=nombre_equipo, ig=integrantes: self._abrir_dialogo_editar_equipo(n, ig)
                          ).grid(row=0, column=1, padx=5, pady=6)
            ctk.CTkButton(fila, text="🗑️ Eliminar", width=90, fg_color="#a13d3d", hover_color="#c94f4f",
                          command=lambda n=nombre_equipo: self._eliminar_equipo(n)).grid(
                row=0, column=2, padx=(0, 10), pady=6)

    def _abrir_dialogo_nuevo_equipo(self):
        EquipoDialog(self, personas=self.data.get("personas", []),
                     on_guardar=self._guardar_equipo, nombre_equipo=None, integrantes=None)

    def _abrir_dialogo_editar_equipo(self, nombre_equipo, integrantes):
        EquipoDialog(self, personas=self.data.get("personas", []),
                     on_guardar=self._guardar_equipo, nombre_equipo=nombre_equipo, integrantes=integrantes)

    def _guardar_equipo(self, nombre, integrantes, nombre_original):
        equipos = self.data.setdefault("equipos", {})
        if nombre_original and nombre_original != nombre and nombre_original in equipos:
            del equipos[nombre_original]
        equipos[nombre] = integrantes
        guardar_datos(JSON_PATH, self.data)
        self._refrescar_todo()
        self._log(f"✅ Equipo guardado: {nombre} ({len(integrantes)} integrante(s))")

    def _eliminar_equipo(self, nombre_equipo):
        if not messagebox.askyesno("Confirmar eliminación", f"¿Eliminar el equipo '{nombre_equipo}'?"):
            return
        equipos = self.data.get("equipos", {})
        if nombre_equipo in equipos:
            del equipos[nombre_equipo]
            guardar_datos(JSON_PATH, self.data)
            self._refrescar_todo()
            self._log(f"🗑️ Equipo eliminado: {nombre_equipo}")

    # ---------------------------------------------------------
    # TERMINAL DE RESULTADOS
    # ---------------------------------------------------------
    def _construir_terminal(self, main):
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=2, column=0, sticky="ew", pady=(10, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Terminal de Resultados",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Limpiar", width=80, fg_color="#2b2b2b", hover_color="#3a3a3a",
                      command=self._limpiar_terminal).grid(row=0, column=1, sticky="e")

        self.terminal = ctk.CTkTextbox(main, height=220, fg_color="#0d0f13", text_color="#e0e0e0",
                                        font=ctk.CTkFont(family="Consolas", size=13))
        self.terminal.grid(row=3, column=0, sticky="nsew")
        main.grid_rowconfigure(3, weight=1)

        fuente_negrita = ctk.CTkFont(family="Consolas", size=13, weight="bold")
        self.terminal._textbox.tag_config("bold", font=fuente_negrita, foreground="#ffffff")

        self.terminal.configure(state="disabled")

    def _mostrar_personas(self, personas):
        """Imprime cada persona en bloque, separadas por línea en blanco,
        SIN deduplicar (cada rol se muestra), ordenadas por categoría."""
        if not personas:
            self._log("No se encontraron coincidencias.")
            return

        personas = ordenar_por_categoria(personas)

        for p in personas:
            puesto = obtener_puesto(p)
            nombre = p.get("nombre", "N/A")
            telefono = p.get("telefono", "N/A")
            email = p.get("email", "N/A")

            texto = (
                f"{puesto}: {nombre}\n"
                f"Teléfono: {telefono}\n"
                f"Email: {email}"
            )
            self._log(texto, bold=True)
            self._log("")

    def _log(self, texto, bold=False):
        self.terminal.configure(state="normal")
        inicio = self.terminal.index("end")
        self.terminal.insert("end", texto + "\n")
        fin = self.terminal.index("end")

        if bold:
            self.terminal._textbox.tag_add("bold", inicio, fin)

        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def _limpiar_terminal(self):
        self.terminal.configure(state="normal")
        self.terminal.delete("1.0", "end")
        self.terminal.configure(state="disabled")


if __name__ == "__main__":
    app = DataApp()
    app.mainloop()