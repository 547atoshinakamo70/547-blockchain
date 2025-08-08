export default {
  async fetch(request, env) {
    // ORIGIN p.ej. "http://2.137.118.154:5000"
    const ORIGIN = env.ORIGIN || "http://127.0.0.1:5000";
    const reqUrl = new URL(request.url);
    const target = new URL(reqUrl.pathname + reqUrl.search, ORIGIN);

    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': request.headers.get('Origin') || '*',
          'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
          'Access-Control-Allow-Headers': request.headers.get('Access-Control-Request-Headers') || '*',
          'Access-Control-Max-Age': '86400'
        }
      });
    }

    const headers = new Headers(request.headers);
    headers.delete('host'); headers.delete('cf-connecting-ip'); headers.delete('cf-ray');

    const init = {
      method: request.method,
      headers,
      body: (request.method === 'GET' || request.method === 'HEAD') ? undefined : await request.arrayBuffer(),
      redirect: 'follow'
    };

    let resp = await fetch(target.toString(), init);
    const outHeaders = new Headers(resp.headers);
    outHeaders.set('Access-Control-Allow-Origin', request.headers.get('Origin') || '*');
    outHeaders.set('Access-Control-Allow-Credentials', 'false');

    return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: outHeaders });
  }
}
