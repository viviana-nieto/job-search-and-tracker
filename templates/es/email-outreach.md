# Plantilla de Correo de Contacto

## Estructura

Cada correo necesita:
1. **5 Variantes de Asunto**
2. **Cuerpo** (3-4 parrafos maximo)
3. **CTA claro** con solicitud especifica

---

## Variantes de Linea de Asunto

Genera 5 opciones de estas categorias:

### 1. Directo
```
Consulta rapida sobre [Role] en [Company]
Oportunidad de [Role] en [Company]
```

### 2. Curiosidad
```
Vi el trabajo de [Company] en [specific thing]
Tu [equipo/producto] llamo mi atencion
```

### 3. Conexion Mutua
```
[Mutual Name] me sugirio contactarte
[Mutual Name] me hablo de tu equipo
```

### 4. Valor Primero
```
[Quantified impact] en [domain], interesado/a en la mision de [Company]
[Title] explorando [Company]
```

### 5. Pregunta
```
15 min para un cafe? [Company] + [your domain]
Podria consultarte sobre [Company]?
```

---

## Plantillas de Cuerpo del Correo

### Plantilla A: Reclutador/RRHH (Contacto Calido)

```
Hola [Name],

[Apertura con conexion personal: contacto mutuo, como los encontraste, o su publicacion]

Se que [reconocimiento: el rol puede estar en proceso, el equipo esta ocupado, etc.], pero me encantaria estar en tu radar. {{cred_medium}}

Si tienes oportunidades de [Role] que puedan ser un buen fit, estoy en busqueda activa y con gusto podemos conectar.

Adjunto mi CV para tu referencia.

{{sign_off_email}}
{{first_name}}
```

### Plantilla B: Hiring Manager/Miembro del Equipo

```
Hola [Name],

Encontre [como los encontraste: su perfil, articulo, la publicacion del rol] y quise escribirte directamente. {{cred_short}}, y el trabajo de [Company] en [specific thing] es exactamente el tipo de problema que me apasiona resolver.

Contexto rapido: {{cred_medium}}

Tendrias 15 minutos para una llamada rapida? Me encantaria saber mas sobre [specific aspect of their work/team].

{{sign_off_email}}
{{first_name}}
```

### Plantilla C: Contacto en Frio (Sin Conexion Mutua)

```
Hola [Name],

Espero que te encuentres bien. Te escribo porque [specific reason: publicacion de rol, noticias de la empresa, su contenido].

Actualmente estoy explorando oportunidades en [industry], y el enfoque de [Company] hacia [specific thing] destaca. {{cred_medium}}

Me encantaria conectar si tienes unos minutos. Te funcionaria el [specific day] o el [specific day] para una llamada breve?

{{sign_off_email}}
{{first_name}}
```

---

## Elementos Clave

### Lineas de Apertura (Elige Una)
- "Mi amigo/a [Name] me compartio tu mensaje sobre..."
- "Encontre tu perfil mientras investigaba..."
- "Vi el anuncio de [Company] sobre..."
- "Recientemente aplique para [Role] y quise escribirte directamente."
- "[Mutual] me menciono que eres la persona indicada para hablar sobre..."

### Arco de Credibilidad (Adaptar Segun el Rol)
- **Completo**: {{cred_long}}
- **Corto**: {{cred_short}}
- **Medio**: {{cred_medium}}

### CTAs (Elige Uno)
- "Tendrias 15 minutos para una llamada rapida?"
- "Con gusto podemos tomar un cafe si estas en [location]."
- "Me encantaria estar en tu radar para futuras oportunidades."
- "Te funcionaria el [day] o el [day] para una charla breve?"
- "Si tienes unos minutos, agradeceria cualquier perspectiva."

### Despedidas
- `{{sign_off_email}}` (predeterminada para correo)
- `{{sign_off_formal}}` (mas formal)

---

## Variables

- `[Name]` - Nombre del destinatario
- `[Company]` - Empresa objetivo
- `[Role]` - Titulo del rol especifico
- `[Mutual Name]` - Conexion mutua
- `[specific thing]` - Producto, mision o noticias de la empresa
- `[industry]` - Tu industria objetivo
- `[specific day]` - Sugerir dias concretos (martes, jueves)

---

## Reglas de Redaccion

Seguir las reglas de config/writing-style.json, ademas de:
1. Mantener parrafos de 2-3 oraciones.
2. Un CTA claro por correo.
3. Adjuntar CV cuando sea apropiado (mencionarlo).
4. Longitud total: Menos de 200 palabras para contacto en frio.
