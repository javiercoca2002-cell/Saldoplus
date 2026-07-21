from database import db
from flask_login import UserMixin
from datetime import datetime

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefono = db.Column(db.String(20), default='')
    password = db.Column(db.String(200), nullable=False)
    saldo_actual = db.Column(db.Float, default=0.0)
    total_ganado = db.Column(db.Float, default=0.0)
    pago_pendiente = db.Column(db.Boolean, default=True)
    es_admin = db.Column(db.Boolean, default=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    operaciones = db.relationship('Operacion', backref='usuario', lazy=True)

class Operacion(db.Model):
    __tablename__ = 'operaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    monto_invertido = db.Column(db.Float, nullable=False)
    monto_retorno = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(20), default='pendiente')
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_completada = db.Column(db.DateTime, nullable=True)
    
    def completar(self):
        self.estado = 'completada'
        self.fecha_completada = datetime.utcnow()
        self.usuario.saldo_actual += self.monto_retorno
        self.usuario.total_ganado += (self.monto_retorno - self.monto_invertido)