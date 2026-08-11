# OpenTimeTrack Core

Servicio de **registro horario** de código abierto, pensado para cumplir el artículo 34.9 del
Estatuto de los Trabajadores (Real Decreto-ley 8/2019) con garantías técnicas de integridad y no
repudio.

Se usa de dos formas, y las dos son de primera clase:

1. **Directamente**, con su panel web y su aplicación móvil.
2. **Delegado desde otra aplicación**: cualquier producto puede autenticar a sus usuarios contra el
   mismo proveedor de identidad, registrar fichajes en su nombre y consumir los datos de asistencia
   por la API. El protocolo de integración es abierto y forma parte de este repositorio.

## Principios

- **El servidor manda el tiempo.** La marca temporal de un fichaje la genera siempre el servidor.
- **Nada se borra.** Fichajes y auditoría son *append-only* o borrado lógico.
- **Toda modificación deja rastro**, con valor anterior y nuevo.
- **Aislamiento entre empresas.** Ninguna consulta cruza el identificador de inquilino.
- **Trazabilidad del origen.** Cada fichaje registra por qué vía entró, y eso llega al informe.

## Estado

**En construcción, sin release todavía.** El diseño está cerrado y el código se está levantando por
fases. La documentación para quien use o quiera contribuir al proyecto llegará con la primera
versión utilizable, escrita para eso; hasta entonces este repositorio no la trae.

## Puesta en marcha

```bash
cp .env.example .env
podman compose up --build
```

## Licencia

**AGPL-3.0.** Ver [LICENSE](LICENSE).

Consumir este servicio **a través de su API REST sobre red** no convierte a la aplicación que lo
consume en obra derivada: la API es el punto de integración previsto y su uso no arrastra la
licencia.

Las contribuciones se aceptan bajo CLA, que permite a Mientras Esperas, S.L. distribuir el código
tanto bajo AGPL-3.0 como en su servicio gestionado.

## Desarrollo

Este repositorio filtra las coautorías de herramientas de IA en los mensajes de commit. Tras
clonar:

```bash
git config core.hooksPath .githooks
```
