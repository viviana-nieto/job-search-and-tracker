# Plantilla de Adaptacion de CV

## Proposito
Adaptar el CV base del usuario a una descripcion de puesto especifica, manteniendo el formato original, la estructura y la veracidad.

## Datos Requeridos
- CV base (desde config: resume_path)
- Descripcion del puesto (texto completo)
- Nombre de la empresa y titulo del puesto

## Reglas de Adaptacion

### Que SI hacer:
- Reordenar los puntos dentro de cada puesto para priorizar la experiencia relevante al JD
- Reflejar palabras clave del JD de forma natural (por ejemplo, si el JD dice "colaboracion interfuncional", usar esa frase si tu experiencia coincide)
- Enfatizar logros cuantificados que se alineen con las areas de enfoque del puesto
- Ajustar el resumen profesional/titular para reflejar el puesto objetivo
- Resaltar habilidades tecnicas mencionadas en el JD que el usuario realmente posee
- Si el JD enfatiza liderazgo, comenzar con puntos de liderazgo. Si enfatiza profundidad tecnica, comenzar con puntos tecnicos.

### Que NO hacer:
- Nunca agregar experiencia, habilidades o logros que el usuario no tenga
- Nunca cambiar titulos de puesto, nombres de empresas o fechas
- Nunca inventar metricas o numeros
- Nunca eliminar puestos por completo (reordenar puntos dentro de los puestos en su lugar)
- Nunca cambiar el formato visual/estructura del CV
- Mantener la misma cantidad de puntos por puesto (no agregar ni eliminar)

### Proceso de Adaptacion:
1. Leer la descripcion del puesto completa cuidadosamente
2. Identificar los 5 requisitos/temas principales del JD
3. Para cada puesto en el CV, reordenar los puntos para que los mas relevantes al JD aparezcan primero
4. Ajustar el resumen profesional para reflejar el puesto objetivo
5. Asegurar que la seccion de habilidades resalte primero las habilidades relevantes al JD
6. Revisar: este CV se lee como alguien que es un candidato natural para ESTE puesto especifico?

## Formato de Salida

Guardar el CV adaptado como markdown, manteniendo la misma estructura de secciones que el original:
- Mismas secciones en el mismo orden
- Mismos puestos en el mismo orden
- Puntos reordenados dentro de cada puesto
- Resumen profesional ajustado

## Variables
- `[Company]` - Empresa objetivo
- `[Role]` - Titulo del puesto objetivo
- `{{name}}` - Desde config
- `{{title}}` - Desde config (puede ajustarse para coincidir con el puesto objetivo)
- `{{email}}`, `{{phone}}`, `{{website}}`, `{{location}}` - Desde config

## Verificacion de Calidad
Despues de adaptar, verificar:
1. Cada punto es factualmente verdadero (existe en el CV base)
2. No se invento informacion nueva
3. El CV se lee de forma natural, no saturado de palabras clave
4. El formato coincide exactamente con el CV original
5. Los 3 requisitos principales del JD estan claramente cubiertos en la primera pagina
