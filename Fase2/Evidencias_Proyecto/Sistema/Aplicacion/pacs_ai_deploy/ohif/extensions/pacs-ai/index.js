/* Minimal OHIF v3 extension: añade un botón "Enviar a IA" a la toolbar */
/* export default {
  id: '@local/extension-pacs-ai',
  preRegistration: () => {},

  getCommandsModule({ servicesManager }) {
    return {
      definitions: {
        'pacsai:sendToAI': {
          commandFn: async () => {
            const { UIDialogService, UINotificationService, DisplaySetService, ViewportGridService } =
              servicesManager.services;

            try {
              const { activeViewportId } = ViewportGridService.getState();
              const dsets = DisplaySetService.getActiveDisplaySetsForViewport?.(activeViewportId) || [];
              const studyUid = dsets?.[0]?.StudyInstanceUID || dsets?.[0]?.studyInstanceUid;

              if (!studyUid) {
                UINotificationService.show({ title: 'PACS-AI', message: 'No se encontró StudyInstanceUID activo.' });
                return;
              }

              UINotificationService.show({ title: 'PACS-AI', message: 'Enviando estudio al backend…' });

              const res = await fetch('http://127.0.0.1:8001/analyze/download-only', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  study_uid: studyUid,
                  orthanc: 'http://127.0.0.1:8042',
                  background: true,
                }),
              });

              if (!res.ok) {
                const txt = await res.text();
                throw new Error(txt || `HTTP ${res.status}`);
              }

              UINotificationService.show({
                title: 'PACS-AI',
                message: '✅ Análisis encolado. El SEG aparecerá en este estudio en ~2–3 s.',
                type: 'success',
                duration: 4000,
              });
            } catch (err) {
              console.error(err);
              servicesManager.services?.UINotificationService?.show({
                title: 'PACS-AI',
                message: `❌ Error al enviar a IA: ${err?.message || err}`,
                type: 'error',
              });
            }
          },
          storeContexts: ['viewports'], // se ejecuta en el modo VIEWER
        },
      },
      // contexto por defecto del módulo de comandos
      defaultContext: ['VIEWER'],
    };
  },

  getToolbarModule({ commandsManager }) {
    return {
      definitions: {
        PacsAiSend: {
          id: 'PacsAiSend',
          label: 'Enviar a IA',
          // usa un icono built-in; 'ai' puede no existir en tu build, 'segmentation' o 'study' sí
          icon: 'segmentation',
          type: 'command',
          commandName: 'pacsai:sendToAI',
          tooltip: 'Enviar estudio a PACS-AI',
        },
      },
      defaultContext: 'VIEWER',
      layout: [
        // agrega el botón al grupo principal
        {
          tools: ['PacsAiSend'],
        },
      ],
    };
  },
};
 */