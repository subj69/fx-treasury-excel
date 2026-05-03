from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
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



@app.get("/export/deals")
async def export_deals(
    username: str = Depends(verify_treasury_credentials),
    format: str = "xlsx"  # xlsx или csv
):
    """Экспорт всех сделок в Excel (XLSX) или CSV"""
    print(f"📤 Export requested by: {username}, format: {format}")
    
    try:
        # Получаем ВСЕ сделки
        history = await state_service.get_deal_history(limit=100000)
        print(f"📊 Found {len(history)} deals for export")
        
        if format.lower() == "xlsx":
            # 🔥 ЭКСПОРТ В EXCEL (XLSX)
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Сделки"
            
            # Заголовки
            headers = [
                "ID", "Дата", "Время", "Пара", "Тип операции", 
                "Объём", "Курс сделки", "Курс ЦБ", "P/L (RUB)"
            ]
            ws.append(headers)
            
            # Стилизация заголовков
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")
                # Автоширина столбца
                col_letter = get_column_letter(cell.column)
                ws.column_dimensions[col_letter].width = 15
            
            # Данные
            for deal in history:
                timestamp = deal.get('timestamp', '')
                if 'T' in timestamp:
                    date_part, time_part = timestamp.split('T')
                    time_part = time_part.split('.')[0]
                else:
                    date_part = timestamp[:10] if len(timestamp) >= 10 else ''
                    time_part = timestamp[11:19] if len(timestamp) > 11 else ''
                
                side_raw = deal.get('side', '')
                side_ru = "ПРОДАЖА клиенту" if side_raw == 'SELL_TO_CLIENT' else "ПОКУПКА у клиента"
                
                # P/L для цветовой индикации
                pl_value = deal.get('realized_pl', 0)
                
                ws.append([
                    deal.get('id', ''),
                    date_part,
                    time_part,
                    deal.get('pair', ''),
                    side_ru,
                    deal.get('amount', 0),
                    deal.get('price', 0),
                    deal.get('cbr_rate', 0),
                    pl_value
                ])
                
                # Цветовая индикация P/L (последний столбец)
                last_cell = ws.cell(row=ws.max_row, column=9)
                if pl_value > 0:
                    last_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # Зелёный
                    last_cell.font = Font(color="006100", bold=True)
                elif pl_value < 0:
                    last_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")  # Красный
                    last_cell.font = Font(color="9C0006", bold=True)
            
            # Форматирование чисел
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=6, max_col=9):
                for cell in row:
                    if cell.column == 6:  # Объём
                        cell.number_format = '#,##0.00'
                    elif cell.column in [7, 8]:  # Курсы
                        cell.number_format = '0.0000'
                    elif cell.column == 9:  # P/L
                        cell.number_format = '#,##0.00'
            
            # Сохраняем в bytes
            from io import BytesIO
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            filename = f"deals_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            print(f"✅ Excel export successful: {filename} ({len(history)} deals)")
            
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
        
        else:
            # CSV (оставляем как запасной вариант)
            output = io.StringIO()
            output.write('\ufeff')  # BOM для Excel
            
            writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow([
                "ID", "Дата", "Время", "Пара", "Тип операции", 
                "Объём", "Курс сделки", "Курс ЦБ", "P/L (RUB)"
            ])
            
            for deal in history:
                timestamp = deal.get('timestamp', '')
                if 'T' in timestamp:
                    date_part, time_part = timestamp.split('T')
                    time_part = time_part.split('.')[0]
                else:
                    date_part = timestamp[:10] if len(timestamp) >= 10 else ''
                    time_part = timestamp[11:19] if len(timestamp) > 11 else ''
                
                side_raw = deal.get('side', '')
                side_ru = "ПРОДАЖА клиенту" if side_raw == 'SELL_TO_CLIENT' else "ПОКУПКА у клиента"
                
                writer.writerow([
                    deal.get('id', ''),
                    date_part,
                    time_part,
                    deal.get('pair', ''),
                    side_ru,
                    f"{deal.get('amount', 0):.2f}",
                    f"{deal.get('price', 0):.4f}",
                    f"{deal.get('cbr_rate', 0):.4f}",
                    f"{deal.get('realized_pl', 0):.2f}"
                ])
            
            output.seek(0)
            filename = f"deals_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
    
    except Exception as e:
        print(f"❌ Export error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


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