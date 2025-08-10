declare module "express" {
  export interface Request { [key: string]: any }
  export interface Response {
    json: (body: any) => void;
    status: (code: number) => Response;
  }
  export interface Express {
    get(path: string, handler: any): void;
    post(path: string, handler: any): void;
  }
}

declare module "ws" {
  export type RawData = any;
  export class WebSocket {
    on(event: string, listener: (...args: any[]) => void): void;
  }
  export class WebSocketServer {
    constructor(options: any);
    on(event: string, listener: (...args: any[]) => void): void;
  }
}
