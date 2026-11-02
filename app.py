import os
from datetime import datetime, date, time
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///tempo_em_foco.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Entre na sua conta para acessar essa página."
login_manager.login_message_category = "info"


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    data_cadastro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tarefas = db.relationship(
        "Tarefa", backref="usuario", cascade="all, delete-orphan"
    )
    disponibilidades = db.relationship(
        "Disponibilidade", backref="usuario", cascade="all, delete-orphan"
    )
    sugestoes = db.relationship(
        "SugestaoReorganizacao", backref="usuario", cascade="all, delete-orphan"
    )

    def get_id(self):
        return str(self.id_usuario)


class Tarefa(db.Model):
    __tablename__ = "tarefa"

    id_tarefa = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False, index=True
    )
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)
    prazo = db.Column(db.DateTime, nullable=False)
    prioridade = db.Column(db.String(10), nullable=False, default="média")
    status = db.Column(db.String(15), nullable=False, default="pendente")
    duracao_estimada_minutos = db.Column(db.Integer, nullable=False)
    data_conclusao = db.Column(db.DateTime)

    sugestoes = db.relationship(
        "SugestaoReorganizacao", backref="tarefa", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "prioridade IN ('baixa','média','alta')", name="ck_tarefa_prioridade"
        ),
        CheckConstraint(
            "status IN ('pendente','concluída')", name="ck_tarefa_status"
        ),
        CheckConstraint(
            "duracao_estimada_minutos > 0", name="ck_tarefa_duracao"
        ),
    )


class Disponibilidade(db.Model):
    __tablename__ = "disponibilidade"

    id_disponibilidade = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False, index=True
    )
    dia_semana = db.Column(db.Integer, nullable=False)  # 1=segunda, 7=domingo
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fim = db.Column(db.Time, nullable=False)

    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 1 AND 7", name="ck_disponibilidade_dia"),
    )


class SugestaoReorganizacao(db.Model):
    __tablename__ = "sugestao_reorganizacao"

    id_sugestao = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False, index=True
    )
    id_tarefa = db.Column(
        db.Integer, db.ForeignKey("tarefa.id_tarefa"), nullable=False
    )
    motivo = db.Column(db.String(255), nullable=False)
    acao_sugerida = db.Column(db.String(30), nullable=False)
    data_geracao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    aceita = db.Column(db.Boolean, nullable=False, default=False)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Usuario, int(user_id))
    except (TypeError, ValueError):
        return None


def tarefa_do_usuario(task_id):
    return Tarefa.query.filter_by(
        id_tarefa=task_id, id_usuario=current_user.id_usuario
    ).first_or_404()


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("tarefas"))
    return render_template("index.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or not email or len(senha) < 8:
            flash("Preencha os campos. A senha deve ter pelo menos 8 caracteres.", "error")
        elif Usuario.query.filter_by(email=email).first():
            flash("Este e-mail já está cadastrado.", "error")
        else:
            usuario = Usuario(
                nome=nome,
                email=email,
                senha_hash=generate_password_hash(senha),
            )
            db.session.add(usuario)
            db.session.commit()
            login_user(usuario)
            flash("Conta criada! Bem-vinda ao Tempo em Foco.", "success")
            return redirect(url_for("tarefas"))

    return render_template("cadastro.html")


@app.route("/entrar", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.senha_hash, senha):
            login_user(usuario)
            return redirect(url_for("tarefas"))

        flash("E-mail ou senha incorretos.", "error")

    # A página inicial pode conter o formulário de login.
    return render_template("index.html")


@app.route("/sair")
@login_required
def sair():
    logout_user()
    return redirect(url_for("index"))


@app.route("/tarefas", methods=["GET", "POST"])
@login_required
def tarefas():
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        prioridade = request.form.get("prioridade", "média").strip().lower()
        prazo_str = request.form.get("prazo", "").strip()
        duracao_str = request.form.get("duracao", "").strip()

        try:
            # Aceita o campo datetime-local (YYYY-MM-DDTHH:MM)
            # e também apenas a data (YYYY-MM-DD) dos arquivos atuais.
            if "T" in prazo_str:
                prazo = datetime.strptime(prazo_str, "%Y-%m-%dT%H:%M")
            else:
                prazo = datetime.strptime(prazo_str, "%Y-%m-%d")

            duracao = int(duracao_str)
            if not titulo or prioridade not in ("baixa", "média", "alta") or duracao <= 0:
                raise ValueError

            tarefa = Tarefa(
                id_usuario=current_user.id_usuario,
                titulo=titulo,
                descricao=descricao or None,
                prazo=prazo,
                prioridade=prioridade,
                duracao_estimada_minutos=duracao,
            )
            db.session.add(tarefa)
            db.session.commit()
            flash("Tarefa cadastrada.", "success")
            return redirect(url_for("tarefas"))

        except ValueError:
            flash("Confira os campos: prazo válido e duração maior que zero.", "error")

    lista_tarefas = Tarefa.query.filter_by(
        id_usuario=current_user.id_usuario
    ).order_by(Tarefa.status.asc(), Tarefa.prazo.asc()).all()

    disponibilidades = Disponibilidade.query.filter_by(
        id_usuario=current_user.id_usuario
    ).order_by(Disponibilidade.dia_semana, Disponibilidade.hora_inicio).all()

    return render_template(
        "tarefas.html", tarefas=lista_tarefas, disponibilidades=disponibilidades
    )


@app.route("/tarefa/<int:task_id>/concluir", methods=["POST"])
@login_required
def concluir_tarefa(task_id):
    tarefa = tarefa_do_usuario(task_id)
    tarefa.status = "concluída"
    tarefa.data_conclusao = datetime.utcnow()
    db.session.commit()
    flash("Tarefa marcada como concluída.", "success")
    return redirect(url_for("tarefas"))


@app.route("/tarefa/<int:task_id>/excluir", methods=["POST"])
@login_required
def excluir_tarefa(task_id):
    tarefa = tarefa_do_usuario(task_id)
    db.session.delete(tarefa)
    db.session.commit()
    flash("Tarefa excluída.", "success")
    return redirect(url_for("tarefas"))


@app.route("/disponibilidade", methods=["POST"])
@login_required
def adicionar_disponibilidade():
    try:
        dia_raw = request.form.get("dia", "0")
        # Suporta número e nomes dos dias da semana enviados pelo formulário.
        dias = {
            "segunda-feira": 1, "terça-feira": 2, "quarta-feira": 3,
            "quinta-feira": 4, "sexta-feira": 5, "sábado": 6, "domingo": 7,
        }
        dia = dias.get(dia_raw.strip().lower(), int(dia_raw) if dia_raw.isdigit() else 0)
        inicio = time.fromisoformat(request.form.get("inicio", ""))
        fim = time.fromisoformat(request.form.get("fim", ""))

        if not 1 <= dia <= 7 or fim <= inicio:
            raise ValueError

        existentes = Disponibilidade.query.filter_by(
            id_usuario=current_user.id_usuario, dia_semana=dia
        ).all()

        if any(inicio < item.hora_fim and fim > item.hora_inicio for item in existentes):
            flash("Esse horário se sobrepõe a outro período cadastrado para o dia.", "error")
        else:
            db.session.add(
                Disponibilidade(
                    id_usuario=current_user.id_usuario,
                    dia_semana=dia,
                    hora_inicio=inicio,
                    hora_fim=fim,
                )
            )
            db.session.commit()
            flash("Disponibilidade adicionada.", "success")

    except ValueError:
        flash("Informe um dia e um intervalo de horários válido.", "error")

    return redirect(url_for("tarefas"))


@app.route("/disponibilidade/<int:availability_id>/excluir", methods=["POST"])
@login_required
def excluir_disponibilidade(availability_id):
    item = Disponibilidade.query.filter_by(
        id_disponibilidade=availability_id,
        id_usuario=current_user.id_usuario,
    ).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Período removido.", "success")
    return redirect(url_for("tarefas"))


@app.route("/sugestoes")
@app.route("/planejamento")
@login_required
def planejamento():
    pendentes = Tarefa.query.filter_by(
        id_usuario=current_user.id_usuario, status="pendente"
    ).order_by(Tarefa.prazo.asc()).all()

    disponibilidades = Disponibilidade.query.filter_by(
        id_usuario=current_user.id_usuario
    ).all()

    # Total semanal cadastrado. Para evitar contar cada dia como se fosse
    # disponibilidade de hoje, mostramos a soma dos períodos informados.
    total_minutos = sum(
        (
            datetime.combine(date.today(), item.hora_fim)
            - datetime.combine(date.today(), item.hora_inicio)
        ).seconds // 60
        for item in disponibilidades
    )
    tarefas_minutos = sum(t.duracao_estimada_minutos for t in pendentes)
    prioridades_altas = sum(1 for t in pendentes if t.prioridade == "alta")

    # Gera recomendações simples, baseadas em regras predefinidas.
    sugestoes = []
    ordenadas = sorted(
        pendentes,
        key=lambda t: (
            {"alta": 0, "média": 1, "baixa": 2}.get(t.prioridade, 3),
            t.prazo,
        ),
    )

    for tarefa in ordenadas:
        if tarefa.prazo.date() < date.today():
            motivo = "O prazo desta tarefa já passou. Revise e atualize a data."
            acao = "revisar prazo"
        elif tarefa.prioridade == "alta":
            motivo = "Esta tarefa tem prioridade alta. Considere reservá-la primeiro."
            acao = "priorizar tarefa"
        else:
            motivo = "Organize esta tarefa conforme o prazo e o tempo disponível."
            acao = "organizar tarefa"

        sugestoes.append({
            "id_tarefa": tarefa.id_tarefa,
            "titulo": tarefa.titulo,
            "prazo": tarefa.prazo,
            "prioridade": tarefa.prioridade,
            "duracao": tarefa.duracao_estimada_minutos,
            "motivo": motivo,
            "acao": acao,
        })

    return render_template(
        "sugestoes.html",
        tarefas=pendentes,
        total_minutos=total_minutos,
        tarefas_minutos=tarefas_minutos,
        prioridades_altas=prioridades_altas,
        sugestoes=sugestoes,
    )


@app.route("/sugestao/<int:suggestion_id>/aceitar", methods=["POST"])
@login_required
def aceitar_sugestao(suggestion_id):
    sugestao = SugestaoReorganizacao.query.filter_by(
        id_sugestao=suggestion_id,
        id_usuario=current_user.id_usuario,
    ).first_or_404()
    sugestao.aceita = True
    db.session.commit()
    flash(
        "Sugestão aceita. Ajuste a tarefa conforme a recomendação; nenhuma alteração automática foi feita.",
        "success",
    )
    return redirect(url_for("planejamento"))


@app.cli.command("init-db")
def init_db():
    """Cria as tabelas do banco. Execute: flask --app app init-db"""
    db.create_all()
    print("Tabelas criadas.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG", "true").lower() == "true")
