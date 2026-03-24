from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from fpdf import FPDF
import openai
import uuid
from datetime import datetime, timedelta
from flask import request

ADMIN_ID = 1

app = Flask(__name__)

app.secret_key = "revellionsecret"

UPLOAD_FOLDER = "storage"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/loja")
def loja():
    return render_template("loja.html")

@app.route("/cursos")
def cursos():
    return render_template("cursos.html")

@app.route("/premium")
def premium():
    return render_template("premium.html")


# chave de sessão

# Rota de registro
@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("revellion.db")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (username,email,password) VALUES (?,?,?)",
            (username, email, password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")


# Rota de login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("revellion.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user is not None:
            if check_password_hash(user[3], password):
                session["user"] = user[1]
                return redirect("/")
            else:
                return "Senha incorreta!"
        else:
                return "Usuário não encontrado!"

# <- isso garante que o GET sempre retorne a página
    return render_template("login.html")

@app.route("/admin")
def admin():

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()

    conn.close()

    return render_template("admin.html", users=users, produtos=produtos)

@app.route("/loja")
def loja_view():
    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # Buscar produtos aprovados
    cursor.execute("SELECT * FROM produtos WHERE aprovado=1")
    produtos = cursor.fetchall()

    compras = []
    if "user_id" in session:
        cursor.execute(
            "SELECT produto_id FROM compras WHERE user_id=?",
            (session["user_id"],)
        )
        compras = [c[0] for c in cursor.fetchall()]

    conn.close()

    return render_template("loja.html", produtos=produtos, compras=compras)

@app.route("/enviar_produto", methods=["GET", "POST"])
def enviar_produto():
    if "user_id" not in session:
        return redirect("/login")  # garante que só usuário logado envia

    if request.method == "POST":
        nome = request.form["nome"]
        descricao = request.form["descricao"]
        preco = request.form["preco"]
        arquivo = request.files["arquivo"]

        filename = secure_filename(arquivo.filename)
        caminho = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        arquivo.save(caminho)

        conn = sqlite3.connect("revellion.db")
        cursor = conn.cursor()

        conn.commit()
        conn.close()

        return "Produto enviado! Aguarde aprovação do Admin."

        return render_template("enviar_produto.html")

@app.route("/aprovar/<int:id>")
def aprovar(id):
    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE produtos SET aprovado=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")

@app.route("/comprar/<int:produto_id>")
def comprar(produto_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO compras (user_id, produto_id) VALUES (?, ?)",
        (session["user_id"], produto_id)
    )

    conn.commit()
    conn.close()

    return redirect("/minhas_compras")

@app.route("/download_seguro/<int:produto_id>")
def download_seguro(produto_id):

    # 🔒 Verificar login
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # 🔍 Verificar se o usuário comprou
    cursor.execute(
        "SELECT * FROM compras WHERE user_id=? AND produto_id=?",
        (session["user_id"], produto_id)
    )

    compra = cursor.fetchone()

    if not compra:
        conn.close()
        return "❌ Você não tem acesso a este produto!"

    # 📦 Buscar arquivo do produto
    cursor.execute(
        "SELECT arquivo FROM produtos WHERE id=?",
        (produto_id,)
    )
    resultado = cursor.fetchone()

    conn.close()

    if not resultado:
        return "❌ Produto não encontrado!"

    caminho = resultado[0]

    # 📥 Liberar download
    return send_from_directory(
        os.path.join(os.getcwd(), "uploads"),
        caminho.split("/")[-1],
        as_attachment=True
    )

@app.route("/criador")
def criador():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # Pega apenas os produtos do usuário logado
    cursor.execute("SELECT * FROM produtos WHERE user_id=?", (session["user_id"],))
    produtos = cursor.fetchall()

    conn.close()

    return render_template("criador.html", produtos=produtos)

@app.route("/criador_upload", methods=["POST"])
def criador_upload():
    if "user_id" not in session:
        return redirect("/login")

    nome = request.form["nome"]
    descricao = request.form["descricao"]
    preco = request.form["preco"]
    arquivo = request.files["arquivo"]

    arquivo.save(f"uploads/{arquivo.filename}")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO produtos (user_id, nome, descricao, preco, arquivo, aprovado) VALUES (?, ?, ?, ?, ?, 0)",
        (session["user_id"], nome, descricao, preco, arquivo.filename)
    )
    conn.commit()
    conn.close()

    return redirect("/criador")

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # Produtos do criador
    cursor.execute(
        "SELECT * FROM produtos WHERE criador_id=?",
        (session["user_id"],)
    )
    produtos = cursor.fetchall()

    # Total de vendas
    cursor.execute("""
    SELECT COUNT(*) FROM compras
    JOIN produtos ON compras.produto_id = produtos.id
    WHERE produtos.criador_id=?
    """, (session["user_id"],))
    vendas = cursor.fetchone()[0]

    # Total ganho
    cursor.execute("""
    SELECT SUM(valor) FROM ganhos WHERE criador_id=?
    """, (session["user_id"],))
    ganhos = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        produtos=produtos,
        vendas=vendas,
        ganhos=ganhos
    )

@app.route("/criar_produto", methods=["GET", "POST"])
def criar_produto():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        nome = request.form["nome"]
        tema = request.form["descricao"]
        preco = request.form["preco"]
        arquivo = request.files.get("arquivo")

        import os
        from fpdf import FPDF

        # 📂 Garantir pasta uploads
        if not os.path.exists("uploads"):
            os.makedirs("uploads")

        # 📄 Se NÃO enviou arquivo → gerar PDF automático
        if not arquivo or arquivo.filename == "":

            conteudo = f"Ebook sobre: {tema}\n\nConteúdo gerado automaticamente para venda no REVELLION."

            caminho = f"uploads/{nome.replace(' ', '_')}.pdf"

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=12)

            for linha in conteudo.split("\n"):
                pdf.multi_cell(0, 8, linha)

            pdf.output(caminho)

        else:
            # 📁 Upload normal
            from werkzeug.utils import secure_filename
            filename = secure_filename(arquivo.filename)
            caminho = f"uploads/{filename}"
            arquivo.save(caminho)

        import sqlite3
        conn = sqlite3.connect("revellion.db")
        cursor = conn.cursor()

        # 💾 SALVAR PRODUTO
        cursor.execute("""
            INSERT INTO produtos (nome, descricao, preco, arquivo, criador_id, aprovado)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (nome, tema, preco, caminho, session["user_id"]))

        # 🔥 PEGAR ID DO PRODUTO
        produto_id = cursor.lastrowid

        # 💰 CRIAR COMISSÃO
        cursor.execute("""
            INSERT INTO comissoes (produto_id, criador_id, percentual_criador, percentual_site)
            VALUES (?, ?, ?, ?)
        """, (produto_id, session["user_id"], 80, 20))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

        return render_template("criar_produto.html")

@app.route("/baixar_arquivo/<path:filename>")
def baixar_arquivo(filename):
    # Busca o arquivo dentro da pasta uploads
    return send_from_directory(os.path.join(os.getcwd(), "uploads"), filename, as_attachment=True)

@app.route("/minhas_compras")
def minhas_compras():

    # 🔒 Verificar se está logado
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # 📦 Buscar produtos comprados pelo usuário
    cursor.execute("""
        SELECT produtos.id, produtos.nome, produtos.descricao, produtos.preco, produtos.arquivo
        FROM compras
        JOIN produtos ON compras.produto_id = produtos.id
        WHERE compras.user_id=?
    """, (session["user_id"],))

    produtos = cursor.fetchall()

    conn.close()

    return render_template("minhas_compras.html", produtos=produtos)

@app.route("/gerar_link/<int:produto_id>")
def gerar_link(produto_id):

    if "user_id" not in session:
        return redirect("/login")

    import uuid
    from datetime import datetime, timedelta

    token = str(uuid.uuid4())
    expira = datetime.now() + timedelta(minutes=10)

    # 🔐 PEGAR IP
    ip = request.remote_addr

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # Verificar compra
    cursor.execute(
        "SELECT * FROM compras WHERE user_id=? AND produto_id=?",
        (session["user_id"], produto_id)
    )

    if not cursor.fetchone():
        conn.close()
        return "❌ Você não comprou este produto"

    # 💾 SALVAR COM IP
    cursor.execute("""
        INSERT INTO downloads 
        (user_id, produto_id, token, expira_em, downloads_restantes, ip)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session["user_id"], produto_id, token, expira, 3, ip))

    conn.commit()
    conn.close()

    return redirect(f"/download/{token}")

@app.route("/download/<token>")
def download_token(token):

    from datetime import datetime

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT produto_id, expira_em, downloads_restantes, ip
        FROM downloads
        WHERE token=?
    """, (token,))

    link = cursor.fetchone()

    if not link:
        return "❌ Link inválido"

    produto_id, expira_em, restantes, ip_guardado = link

    # 🌐 PEGAR IP ATUAL
    ip_atual = request.remote_addr

    # 🔐 VERIFICAR IP
    if ip_atual != ip_guardado:
        return redirect(f"/gerar_link/{produto_id}")

    # ⏳ EXPIRAÇÃO
    if datetime.now() > datetime.fromisoformat(expira_em):
        return "⏳ Link expirado"

    # 🔢 LIMITE
    if restantes <= 0:
        return "🚫 Limite de downloads atingido"

    # 📦 Buscar arquivo
    cursor.execute("SELECT arquivo FROM produtos WHERE id=?", (produto_id,))
    resultado = cursor.fetchone()

    # ➖ Diminuir contador
    cursor.execute("""
        UPDATE downloads
        SET downloads_restantes = downloads_restantes - 1
        WHERE token=?
    """, (token,))

    conn.commit()
    conn.close()

    import os
    return send_from_directory(
        os.path.join(os.getcwd(), "uploads"),
        resultado[0].split("/")[-1],
        as_attachment=True
    )

import requests
import uuid

@app.route("/pagar/<int:produto_id>")
def pagar(produto_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    cursor.execute("SELECT preco FROM produtos WHERE id=?", (produto_id,))
    preco = cursor.fetchone()[0]

    transaction_id = str(uuid.uuid4())

    # 🔐 CONFIG M-PESA
    API_URL = "https://api.vm.co.mz:18352/ipg/v1x/c2bPayment/singleStage/"
    API_KEY = "SUA_API_KEY"
    PUBLIC_KEY = "SUA_PUBLIC_KEY"
    SERVICE_PROVIDER_CODE = "171717"

    payload = {
        "input_TransactionReference": transaction_id,
        "input_CustomerMSISDN": "25884XXXXXXX",  # número do cliente
        "input_Amount": str(preco),
        "input_ServiceProviderCode": SERVICE_PROVIDER_CODE,
        "input_ThirdPartyReference": "REVELLION",
        "input_PurchasedItemsDesc": "Compra de produto"
    }

    headers = {
        "Origin": "*",
        "Authorization": f"Bearer {API_KEY}"
    }

    response = requests.post(API_URL, json=payload, headers=headers)

    # 💾 salvar pagamento como pendente
    cursor.execute("""
        INSERT INTO pagamentos (user_id, produto_id, valor, status, transacao_mpesa)
        VALUES (?, ?, ?, ?, ?)
    """, (session["user_id"], produto_id, preco, "pendente", transaction_id))

    conn.commit()
    conn.close()

    return "📲 Pedido enviado ao M-Pesa. Confirme no seu telefone."

@app.route("/confirmar_pagamento/<int:produto_id>")
def confirmar_pagamento(produto_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # Marcar como pago
    cursor.execute("""
        UPDATE pagamentos
        SET status='pago'
        WHERE user_id=? AND produto_id=? AND status='pendente'
    """, (session["user_id"], produto_id))

    # Registrar compra
    cursor.execute("""
        INSERT INTO compras (user_id, produto_id)
        VALUES (?, ?)
    """, (session["user_id"], produto_id))

    # Buscar preço
    cursor.execute("SELECT preco, criador_id FROM produtos WHERE id=?", (produto_id,))
    preco, criador_id = cursor.fetchone()

    # Buscar comissão
    cursor.execute("""
        SELECT percentual_criador FROM comissoes WHERE produto_id=?
    """, (produto_id,))
    percentual = cursor.fetchone()[0]

    valor_criador = (preco * percentual) / 100

    # Atualizar saldo do criador
    cursor.execute("""
        UPDATE users SET saldo = saldo + ?
        WHERE id=?
    """, (valor_criador, criador_id))

    conn.commit()
    conn.close()

    return redirect("/minhas_compras")

@app.route("/financeiro")
def financeiro():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # 💰 Saldo
    cursor.execute("SELECT saldo FROM users WHERE id=?", (session["user_id"],))
    saldo = cursor.fetchone()[0]

    # 📊 Vendas
    cursor.execute("""
        SELECT produtos.nome, pagamentos.valor, pagamentos.criado_em
        FROM pagamentos
        JOIN produtos ON pagamentos.produto_id = produtos.id
        WHERE pagamentos.status='pago' AND produtos.criador_id=?
    """, (session["user_id"],))

    vendas = cursor.fetchall()

    # 💸 Saques
    cursor.execute("""
        SELECT valor, status, criado_em
        FROM saques
        WHERE user_id=?
    """, (session["user_id"],))

    saques = cursor.fetchall()

    conn.close()

    return render_template("financeiro.html", saldo=saldo, vendas=vendas, saques=saques)

@app.route("/pedir_saque", methods=["POST"])
def pedir_saque():

    if "user_id" not in session:
        return redirect("/login")

    valor = float(request.form["valor"])
    numero = request.form["numero"]

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # Ver saldo
    cursor.execute("SELECT saldo FROM users WHERE id=?", (session["user_id"],))
    saldo = cursor.fetchone()[0]

    if valor > saldo:
        conn.close()
        return "❌ Saldo insuficiente"

    # Descontar saldo
    cursor.execute("""
        UPDATE users SET saldo = saldo - ?
        WHERE id=?
    """, (valor, session["user_id"]))

    # Criar pedido
    cursor.execute("""
        INSERT INTO saques (user_id, valor, status, numero_mpesa, criado_em)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (session["user_id"], valor, "pendente", numero))

    conn.commit()
    conn.close()

    return redirect("/financeiro")

@app.route("/admin_financeiro")
def admin_financeiro():

    # 🔒 Proteção simples (pode melhorar depois)
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # 🔒 NOVA VERIFICAÇÃO (ADICIONADA)
    cursor.execute("SELECT is_admin FROM users WHERE id=?", (session["user_id"],))
    if cursor.fetchone()[0] != 1:
        conn.close()
        return "🚫 Acesso negado"

    # 💸 Saques
    cursor.execute("""
        SELECT saques.id, users.username, saques.valor, saques.numero_mpesa, saques.status, saques.criado_em
        FROM saques
        JOIN users ON saques.user_id = users.id
    """)
    saques = cursor.fetchall()

    # 💰 Ganhos da plataforma
    cursor.execute("""
        SELECT SUM(pagamentos.valor * (comissoes.percentual_site / 100.0))
        FROM pagamentos
        JOIN comissoes ON pagamentos.produto_id = comissoes.produto_id
        WHERE pagamentos.status='pago'
    """)
    ganho = cursor.fetchone()[0]

    conn.close()

    return render_template("admin_financeiro.html", saques=saques, ganho=ganho)

@app.route("/aprovar_saque/<int:saque_id>")
def aprovar_saque(saque_id):

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE saques SET status='pago'
        WHERE id=?
    """, (saque_id,))

    conn.commit()
    conn.close()

    return redirect("/admin_financeiro")

@app.route("/rejeitar_saque/<int:saque_id>")
def rejeitar_saque(saque_id):

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    # Buscar dados do saque
    cursor.execute("""
        SELECT user_id, valor FROM saques WHERE id=?
    """, (saque_id,))
    user_id, valor = cursor.fetchone()

    # Devolver saldo ao usuário
    cursor.execute("""
        UPDATE users SET saldo = saldo + ?
        WHERE id=?
    """, (valor, user_id))

    # Marcar como rejeitado
    cursor.execute("""
        UPDATE saques SET status='rejeitado'
        WHERE id=?
    """, (saque_id,))

    conn.commit()
    conn.close()

    return redirect("/admin_financeiro")

@app.route("/callback_mpesa", methods=["POST"])
def callback_mpesa():

    if not request.is_json:
        return "Erro", 400

    data = request.json

    transaction_id = data.get("input_TransactionReference")
    status = data.get("input_ResultCode")

    conn = sqlite3.connect("revellion.db")
    cursor = conn.cursor()

    if status == "0":  # sucesso

        # Atualizar pagamento
        cursor.execute("""
            UPDATE pagamentos SET status='pago'
            WHERE transacao_mpesa=?
        """, (transaction_id,))

        # Buscar dados
        cursor.execute("""
            SELECT user_id, produto_id, valor
            FROM pagamentos
            WHERE transacao_mpesa=?
        """, (transaction_id,))

        user_id, produto_id, valor = cursor.fetchone()

        # Registrar compra
        cursor.execute("""
            INSERT INTO compras (user_id, produto_id)
            VALUES (?, ?)
        """, (user_id, produto_id))

        # Comissão
        cursor.execute("SELECT criador_id FROM produtos WHERE id=?", (produto_id,))
        criador_id = cursor.fetchone()[0]

        cursor.execute("""
            SELECT percentual_criador FROM comissoes WHERE produto_id=?
        """, (produto_id,))
        percentual = cursor.fetchone()[0]

        valor_criador = (valor * percentual) / 100

        cursor.execute("""
            UPDATE users SET saldo = saldo + ?
            WHERE id=?
        """, (valor_criador, criador_id))

    else:
        cursor.execute("""
            UPDATE pagamentos SET status='falhado'
            WHERE transacao_mpesa=?
        """, (transaction_id,))

    conn.commit()
    conn.close()

    return "OK"

import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
