import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '10s', target: 50 },
    { duration: '20s', target: 150 },
    { duration: '10s', target: 200 },
  ],
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:5000';

export default function () {
  let prompts = [
    "Enviar email a juan@example.com diciendo que su paquete está en camino.",
    "Avisar por SMS al 600-111-222 que la reserva ha sido confirmada.",
    "Manda un correo a marta@app.com: Tienes un nuevo mensaje.",
    "Recordatorio por teléfono al 699888777: cita a las 10:00"
  ];
  
  let payload = JSON.stringify({
    user_input: prompts[Math.floor(Math.random() * prompts.length)]
  });
  
  let params = {
    headers: { 'Content-Type': 'application/json' },
  };

  let createRes = http.post(`${BASE_URL}/v1/requests`, payload, params);
  
  check(createRes, {
    'create status is 201 or 200': (r) => r.status === 201 || r.status === 200,
    'id is present': (r) => JSON.parse(r.body).id !== undefined,
  });

  if (createRes.status === 201 || createRes.status === 200) {
    let id = JSON.parse(createRes.body).id;

    let processRes = http.post(`${BASE_URL}/v1/requests/${id}/process`);
    check(processRes, {
      'process status is 202 or 200': (r) => [200, 202].includes(r.status),
    });

    sleep(0.5); 
    let statusRes = http.get(`${BASE_URL}/v1/requests/${id}`);
    check(statusRes, {
      'status is retrieved': (r) => r.status === 200,
      'status is valid': (r) => ['queued', 'processing', 'sent', 'failed'].includes(JSON.parse(r.body).status),
    });
  }

  sleep(1);
}
