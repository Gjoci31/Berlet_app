from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    DateField,
    IntegerField,
    SubmitField,
    SelectField,
    TextAreaField,
    BooleanField,
    FileField,
)
from wtforms.validators import DataRequired, NumberRange

class PassForm(FlaskForm):
    type = StringField('Típus', validators=[DataRequired()])
    start_date = DateField('Kezdő dátum', validators=[DataRequired()])
    end_date = DateField('Lejárati dátum', validators=[DataRequired()])
    total_uses = IntegerField('Alkalmak száma', validators=[DataRequired(), NumberRange(min=1)])
    user_id = SelectField('Felhasználó', coerce=int, validators=[DataRequired()])
    comment = TextAreaField('Megjegyzés')
    submit = SubmitField('Bérlet létrehozása')


class UserForm(FlaskForm):
    username = StringField('Felhasználónév', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = StringField('Jelszó', validators=[DataRequired()])
    role = SelectField('Szerep', choices=[('user', 'User'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Mentés')


class LoginForm(FlaskForm):
    username = StringField('Felhasználónév', validators=[DataRequired()])
    password = PasswordField('Jelszó', validators=[DataRequired()])
    submit = SubmitField('Bejelentkezés')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Jelszó elküldése')


class EmailSettingsForm(FlaskForm):
    email_from = StringField('Feladó email')
    email_password = PasswordField('Email jelszó')

    user_created_enabled = BooleanField('Felhasználó létrehozásakor')
    user_created_text = TextAreaField('Létrehozás üzenete')

    user_deleted_enabled = BooleanField('Felhasználó törlésekor')
    user_deleted_text = TextAreaField('Törlés üzenete')

    pass_created_enabled = BooleanField('Új bérlet létrehozásakor')
    pass_created_text = TextAreaField('Bérlet létrehozás üzenete')

    pass_deleted_enabled = BooleanField('Bérlet törlésekor')
    pass_deleted_text = TextAreaField('Bérlet törlés üzenete')

    pass_used_enabled = BooleanField('Alkalom változásakor')
    pass_used_text = TextAreaField('Alkalom változás üzenete')

    submit = SubmitField('Mentés')


class RestoreForm(FlaskForm):
    """Form used for uploading a database backup to restore."""
    backup_file = FileField('Backup fájl', validators=[DataRequired()])
    submit = SubmitField('Visszaállítás')
