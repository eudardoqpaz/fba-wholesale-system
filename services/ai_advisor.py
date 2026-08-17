"""
AI Advisor Service - Complete FBA Wholesale Business Guide
MiMo API Integration with comprehensive business knowledge.
"""
import httpx
from typing import Optional
from config import settings

MIMO_API_BASE = "https://api.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5"

SYSTEM_PROMPT = """Eres el mejor asesor de negocios de Amazon FBA Wholesale del mundo. Tienes 20+ anos de experiencia 
ayudando a emprendedores a construir negocios exitosos. Tu cliente es un principiante COMPLETO que tiene:
- Cuenta de Amazon Seller ya creada y verificada
- Empresa LLC registrada en Sterling, Virginia, USA
- Presupuesto inicial limitado ($2,000-$5,000)
- Ganas de aprender pero sin experiencia previa en e-commerce

TU TRABAJO ES GUIARLO EN TODO. Desde cero hasta tener un negocio funcionando.

========== TU CONOCIMIENTO COMPLETO ==========

## 1. EL NEGOCIO DE FBA WHOLESALE - EXPLICACION SIMPLE
- Consiste en comprar productos de MARCAS RECONOCIDAS (Pampers, Tide, LEGO, Hasbro, etc.) 
  a precio de MAYORISTA (directamente del fabricante o distribuidor autorizado)
- Y revenderlos en AMAZON a precio de RETAIL
- Amazon se encarga de almacenar, empacar, enviar, y atender al cliente (FBA)
- Tu ganancia = Precio Amazon - Costo proveedor - Fees de Amazon - Envio
- Es el modelo MAS SEGURO de vender en Amazon porque no necesitas crear marca ni inventar productos

## 2. CUANTO INVERTIR - PRESUPUESTO REALISTA
### Con $1,000-$2,000 (Primer mes)
- Plan Professional Amazon: $39.99/mes
- Keepa API: $49/mes (19 euros)  
- Primer inventario: $800-$1,500
- Etiquetas, empaque, envio: $100-$200
- META: 5-10 productos, aprender el proceso

### Con $3,000-$5,000 (Meses 2-3)
- Re-invertir ganancias + capital fresco
- 15-30 productos activos
- META: $2,000-$5,000 en ventas/mes

### Con $10,000+ (Mes 4+)
- Escalar lo que funciona
- 50+ productos
- META: $10,000+/mes en ventas

## 3. EN QUE INVERTIR - PRODUCTOS GANADORES
### CATEGORIAS RECOMENDADAS para principiantes:
- Home & Kitchen (15% referral) - Mucha demanda, productos simples
- Toys & Games (15%) - Temporada alta Q4 es brutal
- Sports & Outdoors (15%) - Buenos margenes
- Health & Household (15%) - Consumibles = recompra
- Baby Products (15%) - Marcas fuertes (Pampers, Huggies)
- Pet Supplies (15%) - Mercado creciente
- Tools & Home Improvement (15%) - Margenes buenos

### CATEGORIAS A EVITAR:
- Electronics (8% referral, margen muy bajo)
- Clothing (17% referral, muchas devoluciones)
- Grocery (perecederos, problemas de caducidad)
- Jewelry (20% referral, alto riesgo)

### CRITERIOS DE UN BUEN PRODUCTO:
- Precio de venta: $20-$75 (sweet spot)
- ROI minimo: 20% (ideal 25%+)
- Ganancia neta minima: $3/unidad
- BSR menor a 100,000 en su categoria
- Menos de 15-20 FBA sellers
- Amazon NO es seller en el listing
- Precio estable los ultimos 90 dias
- Ventas estimadas: 30+/mes
- Reviews: 50+ (indica demanda)
- Rating: 4.0+ (indica calidad)

## 4. DONDE COMPRAR - PROVEEDORES
### TIER 1: Directo con Marcas (MEJOR precio)
Contactar estas marcas y pedir ser distribuidor:
- Procter & Gamble (Pampers, Tide, Gillette, Crest)
- Unilever (Dove, Axe, Degree)
- Hasbro (Monopoly, Transformers, NERF)
- Mattel (Barbie, Hot Wheels, Fisher-Price)
- 3M (Post-it, Scotch, Command)
- Church & Dwight (Arm & Hammer, OxiClean)
- Clorox (Clorox, Pine-Sol, Glad)
- Reckitt Benckiser (Lysol, Air Wick, Mucinex)
- BIC (Boligrafos, encendedores)
- Rubbermaid (contenedores, organizacion)

COMO CONTACTARLAS:
1. Busca su website, seccion "Wholesale" o "Become a Dealer"
2. Llama y pide el departamento de ventas mayoristas
3. Presentate: "I'm [nombre] from [tu empresa LLC]. We're an authorized retailer 
   interested in carrying your products on Amazon."
4. Necesitas: EIN, business license, referencia bancaria

### TIER 2: Distribuidores Mayoristas
- UNFI (grocery, health, organic)
- DollarDays (general merchandise, bajo minimo)
- Faire.com (marketplace mayorista online)
- Tundra.com (sin comisiones para compradores)
- Wholesale Central (directorio)
- World Wide Brands (directorio certificado, $299 unico pago)

### TIER 3: Clubs Mayoristas (para empezar)
- Costco Business Center (Chantilly, VA - cerca de ti!)
- Sam's Club (multiples ubicaciones en NoVA)
- BJs Wholesale
- Estos son BUENOS para aprender y hacer tus primeras compras

### TIER 4: Online/Liquidacion
- Bulq.com (lotes de liquidacion)
- B-Stock (subastas de inventario de retailers grandes)
- Direct Liquidacion (Walmart, Lowe's)

## 5. COMO COMPRAR - PROCESO PASO A PASO
1. Abre cuenta con el distribuidor (necesitas EIN + Resale Certificate)
2. Pide su PRICE LIST (generalmente es un CSV/Excel)
3. Sube el CSV al SCANNER del sistema
4. El sistema busca datos en Keepa y te dice cuales son rentables
5. Haz tu orden (minimo $300-$500 por proveedor)
6. Recibe el inventario en tu ubicacion
7. Inspecciona, etiqueta con FNSKU de Amazon
8. Crea shipment en Seller Central
9. Envia a los fulfillment centers de Amazon
10. Espera que Amazon reciba (2-7 dias)
11. Tus productos ya estan vendiendose!

## 6. FEES DE AMAZON - NUMEROS REALES
Para un producto de $29.99 que pesa 1.5 lbs:
- Referral Fee (15%): $4.50
- FBA Fee (pick, pack, ship): ~$5.40
- Storage (mensual): ~$0.30
- Inbound Placement: ~$0.40
- TOTAL FEES: ~$10.60

Si lo compraste a $15: GANANCIA = $29.99 - $15 - $10.60 = $4.39 (ROI: 29%)

## 7. IMPUESTOS EN VIRGINIA
- LLC en Virginia: Annual Report $50/anio
- State Income Tax: 2-5.75% escala progresiva
- Sales Tax: Amazon lo COBRA y REMITE por ti (Marketplace Facilitator Law)
- Federal: Reportar en tu tax return (Schedule C si es disregarded entity)
- Self-Employment Tax: 15.3% adicional
- CONTRATA UN CPA que entienda e-commerce

## 8. HERRAMIENTAS NECESARIAS
- Keepa ($19/mes): OBLIGATORIA. Historial de precios, BSR, sellers
- RevSeller ($99/anio): Calculadora rapida en Chrome
- Tactical Arbitrage ($50-80/mes): Escaneo masivo de price lists
- Jungle Scout ($49/mes): Estimador de ventas
- Google Sheets: Tracking de productos e inventario

## 9. ERRORES QUE DEBES EVITAR
1. Comprar sin verificar numeros (USA SIEMPRE la calculadora)
2. Comprar donde Amazon es seller (no puedes competir)
3. Comprar de fuentes no autorizadas (riesgo de suspension)
4. No guardar invoices (Amazon las puede pedir)
5. Comprar demasiado de un producto sin historial
6. Ignorar la temporada de storage fees (Q4 es caro)
7. No reinvertir ganancias (el compounding es la clave)
8. Rendirse en el primer mes (el aprendizaje toma tiempo)

## 10. ROADMAP DE 12 MESES
Mes 1-2: Aprendizaje ($1,000-2,000 inversion) -> Aprender el proceso
Mes 3-4: Validacion ($2,000-5,000) -> Encontrar productos que funcionan
Mes 5-8: Crecimiento ($5,000-10,000) -> Escalar lo que funciona
Mes 9-12: Optimizacion (reinvertir) -> $10,000-20,000+/mes en ventas

## FORMATO DE RESPUESTA
- Responde SIEMPRE en espanol
- Usa lenguaje SIMPLE, como hablar con un amigo
- Da numeros CONCRETOS, no generalidades
- Cuando analices un producto, muestra el desglose completo
- Si algo es riesgoso, di "CUIDADO:" antes
- Siempre da el SIGUIENTE PASO concreto que debe tomar
- Usa ejemplos reales con productos y numeros
"""


class AIAdvisor:
    """AI-powered FBA Wholesale business advisor."""

    def __init__(self):
        self.api_key = settings.mimo_api_key if hasattr(settings, 'mimo_api_key') else ""
        self.base_url = settings.mimo_api_base if hasattr(settings, 'mimo_api_base') else MIMO_API_BASE
        self.model = settings.mimo_model if hasattr(settings, 'mimo_model') else MIMO_MODEL

    async def ask(self, question: str, context: str = "", conversation_history: list = None) -> str:
        """Ask the AI advisor."""
        # Always try AI first, fallback to built-in knowledge
        if self.api_key:
            return await self._call_ai(question, context, conversation_history)
        return self._smart_fallback(question, context)

    async def _call_ai(self, question: str, context: str, history: list) -> str:
        """Call MiMo API."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context:
            messages.append({"role": "system", "content": f"ESTADO ACTUAL DEL NEGOCIO:\n{context}"})
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": question})

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": messages, "max_tokens": 3000, "temperature": 0.7},
                )
                data = resp.json()
                if resp.status_code == 200:
                    return data["choices"][0]["message"]["content"]
                return self._smart_fallback(question, "")
            except Exception:
                return self._smart_fallback(question, "")

    async def analyze_product(self, product_data: dict) -> str:
        """Detailed product analysis."""
        p = product_data
        sell = p.get('amazon_price', 0)
        cost = p.get('supplier_cost', 0)
        roi = p.get('roi_pct', 0)
        profit = p.get('net_profit', 0)
        bsr = p.get('bsr', 0)
        sellers = p.get('fba_seller_count', 0)
        is_amz = p.get('is_amazon_seller', False)
        monthly = p.get('monthly_sales_est', 0)
        reviews = p.get('review_count', 0)
        rating = p.get('rating', 0)
        fba_fee = p.get('fba_fee', 0)

        verdict = "COMPRAR" if roi >= 20 and profit >= 3 and not is_amz and sellers <= 20 else \
                  "INVESTIGAR MAS" if roi >= 10 and profit >= 1.5 else "NO COMPRAR"
        
        risk = "BAJO" if not is_amz and sellers <= 10 and bsr <= 50000 else \
               "MEDIO" if sellers <= 20 and bsr <= 100000 else "ALTO"

        reasons = []
        if is_amz:
            reasons.append("Amazon vende este producto - no puedes competir con ellos")
        if sellers > 20:
            reasons.append(f"Hay {sellers} sellers - demasiada competencia")
        if bsr > 100000:
            reasons.append(f"BSR de {bsr:,} indica ventas lentas")
        if roi < 20:
            reasons.append(f"ROI de {roi}% esta bajo (minimo recomendado: 20%)")
        if profit < 3:
            reasons.append(f"Ganancia de ${profit} por unidad es baja (minimo: $3)")
        if monthly < 10:
            reasons.append(f"Solo ~{monthly} ventas/mes - muy pocas")
        if rating < 4.0 and rating > 0:
            reasons.append(f"Rating de {rating}/5 indica problemas de calidad")

        positives = []
        if not is_amz and sellers <= 10:
            positives.append("Poca competencia - buen potencial")
        if bsr <= 30000:
            positives.append(f"BSR de {bsr:,} indica buenas ventas")
        if roi >= 25:
            positives.append(f"ROI de {roi}% es excelente")
        if monthly >= 100:
            positives.append(f"~{monthly} ventas/mes es muy bueno")
        if reviews >= 200:
            positives.append(f"{reviews} reviews indica producto establecido")

        return f"""ANALISIS DE PRODUCTO
{'='*50}

PRODUCTO: {p.get('title', 'N/A')[:60]}
ASIN: {p.get('asin', 'N/A')}

NUMEROS:
  Precio venta Amazon:  ${sell:.2f}
  Costo proveedor:      ${cost:.2f}
  FBA Fee:              ${fba_fee:.2f}
  GANANCIA NETA:        ${profit:.2f}
  ROI:                  {roi}%

MERCADO:
  BSR:                  {bsr:,}
  Sellers FBA:          {sellers}
  Ventas/mes:           ~{monthly}
  Reviews:              {reviews}
  Rating:               {rating}/5
  Amazon vende?:        {'SI - PELIGRO' if is_amz else 'No - Bien'}

{'='*50}
VEREDICTO:  {verdict}
RIESGO:     {risk}
{'='*50}

{'PROBLEMAS ENCONTRADOS:' if reasons else ''}
{chr(10).join('  - ' + r for r in reasons)}

{'ASPECTOS POSITIVOS:' if positives else ''}
{chr(10).join('  + ' + p for p in positives)}

{'RECOMENDACION: Busca otro producto. Los numeros no dan.' if verdict == 'NO COMPRAR' else ''}
{'RECOMENDACION: Analiza mas a fondo antes de comprar.' if verdict == 'INVESTIGAR MAS' else ''}
{'RECOMENDACION: Buen producto! Haz una orden pequena primero para probar.' if verdict == 'COMPRAR' else ''}"""

    async def daily_briefing(self, business_data: dict) -> str:
        """Daily business briefing."""
        d = business_data
        if not d.get('total_products'):
            return """BRIEFING DIARIO
{'='*50}

ESTADO: Sin productos aun.

PRIORIDAD #1: Agrega tus primeros productos.

Pasos concretos HOY:
1. Ve a /scanner -> Product Finder
2. Busca en "Home & Kitchen" con precio $20-75, max BSR 50000
3. Analiza los 5 mejores resultados
4. Agrega los rentables (ROI > 20%) a tu lista
5. Contacta un distribuidor para obtener precios

No necesitas hacer todo hoy. Empieza con el paso 1."""

        profitable = d.get('profitable_count', 0)
        total = d.get('total_products', 0)
        fba = d.get('total_fba_units', 0)
        invested = d.get('total_invested', 0)

        status = "Excelente" if profitable > total * 0.7 else \
                 "Bien" if profitable > total * 0.5 else "Necesita atencion"

        return f"""BRIEFING DIARIO
{'='*50}

ESTADO GENERAL: {status}

METRICAS:
  Productos activos:    {total}
  Rentables:            {profitable} ({round(profitable/total*100) if total else 0}%)
  Unidades en FBA:      {fba}
  Total invertido:      ${invested:.2f}
  Stock bajo:           {d.get('low_stock', 0)}
  Sin stock:            {d.get('out_of_stock', 0)}
  Alertas pendientes:   {d.get('alerts_count', 0)}

PRIORIDADES HOY:
  {'1. Reordena productos con stock bajo' if d.get('low_stock', 0) > 0 else '1. Busca nuevos productos en el Scanner'}
  {'2. Revisa productos no rentables - elimina o ajusta precio' if profitable < total * 0.5 else '2. Reordena los que mas se venden'}
  3. {'Revisa alertas pendientes' if d.get('alerts_count', 0) > 0 else 'Busca nuevos proveedores'}

CONSEJO SEMANAL:
  {'Tu catalogo esta pequeno. Agrega mas productos para diversificar.' if total < 10 else ''}
  {'Tienes buenos productos! Enfocate en reordenar los rentables.' if profitable > total * 0.5 else ''}
  {'Demasiados productos no rentables. Analiza cuales vale la pena mantener.' if profitable < total * 0.3 else ''}"""

    def _smart_fallback(self, question: str, context: str) -> str:
        """Intelligent fallback when API is not available."""
        q = question.lower()

        if any(w in q for w in ["empezar", "comenzar", "primer", "inicio", "start", "como empiezo"]):
            return """COMO EMPEZAR EN FBA WHOLESALE - PASO A PASO
{'='*50}

Ya tienes la cuenta de Amazon y la empresa. Perfecto. Ahora sigue estos pasos:

SEMANA 1 - PREPARACION:
  1. Contrata Keepa ($19/mes) - keepa.com/#!api
  2. Instala la extension de Chrome de Keepa
  3. Aprende a leer graficos de Keepa (YouTube: "Keepa tutorial wholesale")
  4. Abre tu Resale Certificate en Virginia (tax.virginia.gov)

SEMANA 2 - PRIMEROS PRODUCTOS:
  1. Ve a /scanner -> Product Finder
  2. Categoria: "Home & Kitchen"
  3. Precio: $20-$75
  4. Max BSR: 50,000
  5. Max FBA Sellers: 15
  6. Excluir Amazon: SI
  7. Busca y analiza los resultados

SEMANA 3 - PRIMER PROVEEDOR:
  1. Registra tu empresa en 2-3 distribuidores online
  2. Pide sus price lists (CSV)
  3. Sube el CSV al Scanner del sistema
  4. El sistema te dice cuales son rentables

SEMANA 4 - PRIMERA COMPRA:
  1. Selecciona 3-5 productos rentables
  2. Inversion: $500-$1,000
  3. Compra al distribuidor
  4. Recibe, inspecciona, etiqueta
  5. Envia a Amazon FBA

INVERSION INICIAL NECESARIA:
  Keepa:                    $19/mes
  Amazon Professional:      $39.99/mes
  Primer inventario:        $500-$1,000
  Etiquetas + empaque:      $50
  Envio a Amazon:           $30-$50
  TOTAL:                    ~$650-$1,150

NO NECESITAS MAS QUE ESTO PARA EMPEZAR."""

        elif any(w in q for w in ["invertir", "presupuesto", "cuanto cuesta", "cuanto necesito", "dinero", "capital"]):
            return """CUANTO INVERTIR - PRESUPUESTO REALISTA
{'='*50}

NIVEL 1 - EMPEZAR ($650-$1,200):
  Amazon Professional:      $39.99/mes
  Keepa:                    $19/mes (19 euros)
  Primer inventario:        $500-$800
  Materiales:               $50
  Envio:                    $30-$50
  META: 3-5 productos, aprender el proceso

NIVEL 2 - CRECER ($2,000-$5,000):
  Todo lo anterior
  Inventario ampliado:      $1,500-$3,000
  Herramientas extra:       $50-$100/mes
  META: 15-30 productos, $3,000-$8,000 ventas/mes

NIVEL 3 - ESCALAR ($10,000+):
  Re-invertir ganancias
  50+ productos
  META: $15,000-$50,000+ ventas/mes

COMO DISTRIBUIR EL PRESUPUESTO:
  70% -> Inventario (productos rentables)
  15% -> Herramientas (Keepa, etc.)
  10% -> Envio y materiales
  5%  -> Reserva para emergencias

REGLA DE ORO: Empieza pequeno. No inviertas todo de una vez.
Compra 3-5 productos, aprende, y reinvierte las ganancias."""

        elif any(w in q for w in ["donde comprar", "proveedor", "supplier", "distributor", "distribuidor", "marca"]):
            return """DONDE COMPRAR - GUIA COMPLETA DE PROVEEDORES
{'='*50}

METODO 1: DIRECTO CON MARCAS (mejor precio)
  Contacta estas marcas y pregunta por wholesale:
  - Procter & Gamble (Pampers, Tide, Gillette)
  - Unilever (Dove, Axe, Degree)
  - Hasbro (Monopoly, NERF, Transformers)
  - Mattel (Barbie, Hot Wheels)
  - 3M (Post-it, Scotch, Command)
  - Clorox (Clorox, Pine-Sol, Glad)
  - BIC (boligrafos, encendedores)
  
  COMO: Busca "[marca] wholesale" o "[marca] become a dealer"
  NECESITAS: EIN, business license, referencia bancaria

METODO 2: DISTRIBUIDORES ONLINE (mas facil)
  - Faire.com - marketplace mayorista
  - Tundra.com - sin comisiones
  - DollarDays - bajo minimo de compra
  - UNFI - grocery y health
  
METODO 3: CLUBS LOCALES (para empezar)
  - Costco Business Center (Chantilly, VA - cerca de ti!)
  - Sam's Club
  - BJs Wholesale

METODO 4: LIQUIDACION
  - Bulq.com - lotes de liquidacion
  - B-Stock - subastas de retailers

EMPIEZA CON: Costco Business Center + 1 distribuidor online.
Despues expande a marcas directas."""

        elif any(w in q for w in ["producto", "rentable", "roi", "ganancia", "cuanto gano", "numeros"]):
            return """COMO SABER SI UN PRODUCTO ES RENTABLE
{'='*50}

USA LA CALCULADORA del sistema (en el menu).

NUMEROS MINIMOS para comprar:
  ROI:              20%+ (ideal 25%+)
  Ganancia neta:    $3+ por unidad
  BSR:              < 100,000
  Sellers FBA:      < 20 (ideal < 15)
  Amazon seller:    NO
  Ventas/mes:       30+
  Precio:           $20-$75

EJEMPLO REAL:
  Producto: Pampers Swaddlers (talla 3, 136 count)
  Precio Amazon:    $49.99
  Costo proveedor:  $32.00
  Referral fee:     -$7.50 (15%)
  FBA fee:          -$6.50
  Storage:          -$0.40
  GANANCIA:         $3.59
  ROI:              11.2% -> MARGINAL

  MEJOR OPCION: Buscar un producto similar con mejor margen.

USA EL SCANNER para analizar productos automaticamente."""

        elif any(w in q for w in ["briefing", "resumen", "estado", "como voy", "como va"]):
            return """BRIEFING DE TU NEGOCIO
{'='*50}

Para ver un briefing completo, usa el boton "Briefing" en esta pagina
o ve al Dashboard principal.

El briefing incluye:
- Estado general del negocio
- Productos rentables vs no rentables
- Alertas de stock
- Prioridades del dia
- Recomendaciones para crecer

Si no tienes productos aun, el briefing te dira exactamente
que hacer para empezar."""

        else:
            return f"""Soy tu asesor de FBA Wholesale. Puedo ayudarte con:

  - COMO EMPEZAR desde cero
  - CUANTO INVERTIR y en que
  - DONDE ENCONTRAR proveedores
  - ANALIZAR si un producto es rentable
  - EXPLICAR cualquier concepto del negocio
  - GUIARTE paso a paso

Preguntame algo como:
  "Como empiezo?"
  "Cuanto necesito invertir?"
  "Donde encuentro proveedores?"
  "Que es ROI?"
  "Dame un briefing de mi negocio"

O usa los botones de abajo para preguntas rapidas."""


ai_advisor = AIAdvisor()
