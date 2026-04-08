# Plantilla de Solicitud de Conexion en LinkedIn

## Restricciones
- **Maximo 300 caracteres** (limite de LinkedIn)
- Debe incluir: Gancho, credibilidad, CTA suave
- Firmar con `{{sign_off_linkedin}}`

## Estructura

```
[Saludo calido], [contexto especifico sobre la persona/rol]. [Credibilidad breve]. [CTA suave]! {{sign_off_linkedin}}
```

## Elementos del Patron

1. **Saludo calido**: "Hola [Name]," o "Hola [Name], espero que tu semana vaya bien."
2. **Contexto especifico**: Rol al que aplicaste, su contenido, interes mutuo, experiencia compartida
3. **Credibilidad breve**: Una linea contundente ({{cred_short}})
4. **Gancho de valor**: Lo que aportas
5. **CTA suave**: "Me encantaria conectar!" o "Me gustaria saber mas sobre [X]!"
6. **Despedida**: `{{sign_off_linkedin}}`

## Patrones de Ejemplo

### Aplicaste a un Rol
```
Hola [Name], espero que tu semana vaya bien. Aplique para el rol de [Role] en [Company] y encontre tu perfil. Tengo {{cred_short}} y me encantaria conectar con alguien que conoce tan bien este espacio! {{sign_off_linkedin}}
```

### Viste su Contenido
```
Hola [Name], vi tu publicacion sobre [topic] y me encanto tu perspectiva. {{cred_short}}. Me encantaria conectar! {{sign_off_linkedin}}
```

### Conexion Mutua
```
Hola [Name], [Mutual] me menciono que estas haciendo un gran trabajo en [Company]. Estoy explorando roles de [target role] y me encantaria conectar. {{cred_short}}. {{sign_off_linkedin}}
```

### Misma Empresa Objetivo
```
Hola [Name], estoy explorando oportunidades en [Company] y vi que estas en el equipo de [Team]. Me gustaria saber mas sobre la cultura ahi. {{cred_short}}. {{sign_off_linkedin}}
```

## Variables a Completar

- `[Name]` - Nombre de la conexion
- `[Company]` - Empresa objetivo
- `[Role]` - Titulo del rol especifico
- `[Mutual]` - Nombre de la conexion mutua (si aplica)
- `[Team]` - Su equipo en la empresa

## Verificacion de Caracteres

Antes de finalizar, verifica que el mensaje tenga menos de 300 caracteres. Si excede, recorta:
1. "espero que tu semana vaya bien" (usa solo "Hola [Name],")
2. Reduce la credibilidad a su forma mas corta
3. Simplifica el CTA
