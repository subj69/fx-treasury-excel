from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.core.config import get_settings
from app.core.security import verify_treasury_credentials
from app.services.pricing_service import PricingService
from app.services.risk_service import RiskService
from app.services.state_service import StateService
from app.services.cbr_service import CBRService
import json
import uuid

settings = get_settings()
pricing_service = PricingService()
risk_service = RiskService()
state_service = StateService()
cbr_service = CBRService()

app = FastAPI(title="FX Treasury System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.treasury_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket, is_treasury: bool = False):
        await websocket.accept()
        self.active_connections.append(websocket)
        if is_treasury:
            self.treasury_connections.append(websocket)
            print(f"✅ Treasury connected! Total: {len(self.treasury_connections)}")
    
    def disconnect(self, websocket: WebSocket, is_treasury: bool = False):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if is_treasury and websocket in self.treasury_connections:
            self.treasury_connections.remove(websocket)
            print(f"❌ Treasury disconnected! Remaining: {len(self.treasury_connections)}")
    
    async def broadcast_to_treasury(self, message: dict):
        print(f"📤 Broadcasting: {message.get('type')} to {len(self.treasury_connections)} connections")
        for connection in self.treasury_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:
                if connection in self.treasury_connections:
                    self.treasury_connections.remove(connection)

manager = ConnectionManager()
pending_rfqs = {}











# Найдите в main.py блок startup_event и замените его на этот:

@app.on_event("startup")
async def startup_event():
    print("🚀 Starting application...")
    await state_service.init_db()
    
    # 🔥 ВАЖНО: Вместо простой загрузки, мы пересчитываем позицию по истории сделок
    await state_service.recalculate_positions_from_history()
    
    await cbr_service.get_rate("USD")
    await cbr_service.get_rate("EUR")
    print(f"✅ System Ready. Positions: {state_service.positions}")



@app.on_event("shutdown")
async def shutdown_event():
    print("💾 Saving positions before shutdown...")
    await state_service.save_positions_to_db()

@app.get("/")
async def root():
    return HTMLResponse(open("app/templates/client.html", encoding="utf-8").read())

@app.get("/treasury")
async def treasury_page(username: str = Depends(verify_treasury_credentials)):
    return HTMLResponse(open("app/templates/treasury.html", encoding="utf-8").read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    is_treasury = websocket.query_params.get("role") == "treasury"
    print(f"🔌 New connection - Role: {websocket.query_params.get('role', 'client')}")
    await manager.connect(websocket, is_treasury=is_treasury)
    
    try:
        if is_treasury:
            # 🔥 Отправляем полное состояние казначею
            cbr_rates = cbr_service.get_all_rates()
            history = await state_service.get_deal_history(50)
            
            print(f"📤 Sending init_state to treasury")
            print(f"   Positions: {state_service.positions}")
            print(f"   CBR rates: {cbr_rates}")
            print(f"   History: {len(history)} deals")
            
            await websocket.send_json({
                'type': 'init_state',
                'positions': state_service.positions,
                'cbr_rates': cbr_rates,
                'history': history
            })
        
        while True:
            if websocket.client_state.value >= 3:
                print("🔌 Connection already closed, breaking loop")
                break
                
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                print("🔌 WebSocketDisconnect caught")
                break
            except RuntimeError as e:
                if "disconnect" in str(e).lower():
                    print(f"🔌 Connection closed: {e}")
                    break
                raise
            
            print(f"📩 Received: {data.get('type')}")
            req_type = data.get('type')
            
            if req_type == 'new_rfq':
                rfq_id = data.get('rfq_id', str(uuid.uuid4())[:8])
                amount = float(data['amount'])
                pair = data['pair']
                side = data['side']
                
                current_pos = state_service.positions.get(pair, {}).get("amount", 0)
                risk_check = risk_service.check_position_limit(pair, current_pos, amount, side)
                
                pending_rfqs[rfq_id] = {
                    "client_ws": websocket, 
                    "details": data,
                    "created_at": datetime.now()
                }
                
                cbr_rate = cbr_service.get_all_rates().get(pair, 0)
                suggested_price = pricing_service.calculate_suggested_price(cbr_rate, side)
                
                await manager.broadcast_to_treasury({
                    'type': 'incoming_rfq',
                    'rfq_id': rfq_id,
                    'pair': pair,
                    'amount': amount,
                    'side': side,
                    'time': datetime.now().strftime("%H:%M:%S"),
                    'current_pos': {"amount": current_pos},
                    'cbr_rate': cbr_rate,
                    'suggested_price': suggested_price,
                    'risk_warning': risk_check.get('message') if not risk_check['ok'] else None
                })
                print("✅ RFQ broadcasted to treasury")
            
            elif req_type == 'treasury_answer':
                rfq_id = data['rfq_id']
                price = float(data['price'])
                rfq = pending_rfqs.get(rfq_id)
                if rfq and rfq['client_ws']:
                    await rfq['client_ws'].send_json({
                        'type': 'quote_response',
                        'price': price,
                        'pair': rfq['details']['pair'],
                        'amount': rfq['details']['amount'],
                        'side': rfq['details']['side'],
                        'rfq_id': rfq_id
                    })
                    print(f"✅ Quote {price} sent to client")
            
            elif req_type == 'accept_deal':
                pair = data['pair']
                amount = float(data['amount'])
                price = float(data['price'])
                side = data['side']
                
                cbr_rate = await cbr_service.get_rate(pair.replace('/RUB', '')) or 0
                pl = pricing_service.calculate_deal_pl(amount, price, cbr_rate, side)
                
                state_service.update_position(pair, amount, side, price)
                await state_service.save_deal(pair, amount, price, side, cbr_rate, pl)
                await state_service.save_positions_to_db()  # 🔥 Сохраняем сразу
                
                if data.get('rfq_id') in pending_rfqs:
                    del pending_rfqs[data['rfq_id']]
                
                await manager.broadcast_to_treasury({
                    'type': 'deal_update',
                    'positions': state_service.positions,
                    'deal': {
                        'pair': pair, 'amount': amount, 'price': price,
                        'side': side, 'cbr': cbr_rate, 'pl': pl,
                        'time': datetime.now().strftime("%H:%M:%S")
                    }
                })
                await websocket.send_json({
                    'type': 'deal_confirmed',
                    'pl': pl,
                    'new_position': state_service.positions[pair]['amount']
                })
            
            elif req_type == 'reject_quote':
                rfq_id = data['rfq_id']
                if rfq_id in pending_rfqs:
                    del pending_rfqs[rfq_id]
                await manager.broadcast_to_treasury({
                    'type': 'rfq_processed', 'rfq_id': rfq_id
                })
    
    except WebSocketDisconnect:
        print("🔌 WebSocketDisconnect in outer try")
    finally:
        manager.disconnect(websocket, is_treasury=is_treasury)
        to_remove = [k for k, v in pending_rfqs.items() if v['client_ws'] == websocket]
        for k in to_remove:
            del pending_rfqs[k]
            print(f"🗑️ Cleaned RFQ: {k}")
        print("✅ WebSocket handler finished")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)