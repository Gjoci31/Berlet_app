from flask_wtf import FlaskForm
from wtforms import StringField, DateField, IntegerField, SubmitField, SelectField
from wtforms.validators import DataRequired, NumberRange

class PassForm(FlaskForm):
    type = StringField('Típus', validators=[DataRequired()])
    start_date = DateField('Kezdő dátum', validators=[DataRequired()])
    end_date = DateField('Lejárati dátum', validators=[DataRequired()])
    total_uses = IntegerField('Alkalmak száma', validators=[DataRequired(), NumberRange(min=1)])
    user_id = SelectField('Felhasználó', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Bérlet létrehozása')