from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, login_manager
from models import Usuario, Operacion
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave-super-secreta-saldoplus-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///saldoplus.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def crear_admin():
    admin = Usuario.query.filter_by(email='admin@saldoplus.com').first()
    if not admin:
        admin = Usuario(
            nombre='Administrador',
            email='admin@saldoplus.com',
            password=generate_password_hash('admin123'),
            es_admin=True,
            pago_pendiente=False
        )
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        telefono = request.form.get('telefono')
        password = request.form.get('password')
        
        if Usuario.query.filter_by(email=email).first():
            flash('Este email ya esta registrado', 'error')
            return redirect(url_for('registro'))
        
        usuario = Usuario(
            nombre=nombre,
            email=email,
            telefono=telefono,
            password=generate_password_hash(password)
        )
        db.session.add(usuario)
        db.session.commit()
        
        flash('Cuenta creada exitosamente. Ahora transfiere 25 CUP al 56241574 para activar tu saldo.', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and check_password_hash(usuario.password, password):
            login_user(usuario)
            if usuario.es_admin:
                return redirect(url_for('admin'))
            return redirect(url_for('dashboard'))
        
        flash('Email o contrasena incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    operaciones = Operacion.query.filter_by(usuario_id=current_user.id).order_by(Operacion.fecha_creacion.desc()).all()
    return render_template('dashboard.html', operaciones=operaciones)

@app.route('/invertir', methods=['POST'])
@login_required
def invertir():
    monto = float(request.form.get('monto', 0))
    
    if monto != 25:
        flash('El monto de inversion debe ser 25 CUP', 'error')
        return redirect(url_for('dashboard'))
    
    if current_user.saldo_actual < monto:
        flash('No tienes suficiente saldo disponible. Primero transfiere 25 CUP al 56241574.', 'error')
        return redirect(url_for('dashboard'))
    
    operacion = Operacion(
        usuario_id=current_user.id,
        monto_invertido=monto,
        monto_retorno=monto * 1.3
    )
    
    current_user.saldo_actual -= monto
    
    db.session.add(operacion)
    db.session.commit()
    
    flash(f'Inversion de {monto} CUP creada exitosamente. En 3-5 dias recibiras {monto * 1.3:.2f} CUP.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/operaciones')
@login_required
def operaciones():
    ops = Operacion.query.filter_by(usuario_id=current_user.id).order_by(Operacion.fecha_creacion.desc()).all()
    return render_template('operaciones.html', operaciones=ops)

@app.route('/admin')
@login_required
def admin():
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))
    
    usuarios = Usuario.query.filter_by(es_admin=False).all()
    operaciones = Operacion.query.order_by(Operacion.fecha_creacion.desc()).all()
    total_invertido = sum(op.monto_invertido for op in operaciones if op.estado != 'cancelada')
    total_pagado = sum(op.monto_retorno for op in operaciones if op.estado == 'completada')
    
    return render_template('admin.html', 
                         usuarios=usuarios, 
                         operaciones=operaciones,
                         total_invertido=total_invertido,
                         total_pagado=total_pagado)

@app.route('/admin/completar/<int:operacion_id>')
@login_required
def completar_operacion(operacion_id):
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))
    
    operacion = Operacion.query.get(operacion_id)
    if operacion and operacion.estado == 'pendiente':
        operacion.completar()
        db.session.commit()
        flash(f'Operacion #{operacion.id} completada. Se acreditaron {operacion.monto_retorno} CUP al usuario.', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/cancelar/<int:operacion_id>')
@login_required
def cancelar_operacion(operacion_id):
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))
    
    operacion = Operacion.query.get(operacion_id)
    if operacion and operacion.estado == 'pendiente':
        operacion.estado = 'cancelada'
        operacion.usuario.saldo_actual += operacion.monto_invertido
        db.session.commit()
        flash(f'Operacion #{operacion.id} cancelada. Se devolvieron {operacion.monto_invertido} CUP al usuario.', 'info')
    
    return redirect(url_for('admin'))

@app.route('/admin/agregar-saldo/<int:usuario_id>', methods=['POST'])
@login_required
def agregar_saldo(usuario_id):
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))
    
    usuario = Usuario.query.get(usuario_id)
    monto = float(request.form.get('monto', 0))
    
    if usuario and monto > 0:
        usuario.saldo_actual += monto
        usuario.pago_pendiente = False
        db.session.commit()
        flash(f'Se agregaron {monto} CUP a {usuario.nombre}. Pago confirmado.', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/confirmar-pago/<int:usuario_id>')
@login_required
def confirmar_pago(usuario_id):
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))
    
    usuario = Usuario.query.get(usuario_id)
    if usuario:
        usuario.pago_pendiente = False
        db.session.commit()
        flash(f'Pago confirmado para {usuario.nombre}. Ya puede invertir.', 'success')
    
    return redirect(url_for('admin'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        crear_admin()
    app.run(debug=True, host='0.0.0.0', port=5000)