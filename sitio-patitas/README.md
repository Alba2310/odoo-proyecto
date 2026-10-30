# Sitio web de venta de Patitas

Página única para vender Patitas (módulo `extra-addons/veterinaria`). A pedido, no se parece en nada a los sitios de
AutoFlow, Studio Bella ni Óga: es divertida y se juega. Estilo de juguete (bordes negros gruesos, sombras duras,
colores fuertes, cosas un poco torcidas), letras Lilita One y Nunito. Se ve en http://localhost:5503 (servicio
`sitio-patitas` de `docker-compose.yml`).

## Qué tiene

1. **La mascota**: un perro dibujado en SVG que sigue el puntero con los ojos, ladra al tocarlo (el sonido se arma con
   el navegador, no hay archivos de audio) y se vuelve gato con el botón "Soy más de gatos". A los 7 toques, lluvia
   de huellas.
2. **Un día en Patitas**: al bajar, el reloj va de 07:30 a 21:00 y el cielo cambia (amanecer, mediodía, atardecer,
   noche con estrellas); cada hora muestra algo que resuelve el sistema (turno por internet, tablero, sin turno, carnet
   con sello, aviso de WhatsApp, internación, cobro mixto, recordatorios de la noche).
3. **El juego "¡Que no se te junte la sala!"** (`js/juego.js`): 60 segundos, mascotas que llegan, consultorio con dos
   lugares, cobrar, tres vidas. Se arrastra o se toca. Guarda el récord en el navegador y se puede desafiar a un colega
   por WhatsApp.
4. **Álbum de figuritas**: las 12 funciones, cada una se da vuelta; con el álbum completo hay festejo.
5. **Precios como chapitas de collar** que se hamacan: Cachorro, Mediano y Gran danés.
6. **Preguntas peludas**: preguntas y respuestas como charla entre mascotas. Honestas: WhatsApp con un toque (sin la
   API paga), sin SIFEN por ahora.
7. **Dejá tu huella**: el formulario arma el mensaje y abre WhatsApp al número de `CONFIG.whatsapp` (no se guarda nada).
8. Secreto: escribir "guau" o "miau" en cualquier parte de la página hace llover huellas.

## Para cambiar

- **Contacto, precios y la dirección de la página de turnos de prueba**: `CONFIG` al principio de `js/main.js`. Los
  precios son de referencia. `demoTurnos` apunta a la base de ejemplo (http://patitas.localhost:8073/reservar); para
  publicar el sitio hay que cambiarla o dejarla vacía (el enlace desaparece).
- **Las figuritas**: `FIGURITAS` en `js/main.js`.
- **Las horas del día**: los `<article class="paso">` de `index.html` (`data-hora` y `data-momento`, que elige el cielo).
- **El juego**: las constantes al principio de `js/juego.js` (duración, paciencia, lugares del consultorio).
- Con "reducir movimiento" activado en el sistema, las animaciones se apagan.
- El ícono (`img/icon.png`) es el mismo del módulo.
