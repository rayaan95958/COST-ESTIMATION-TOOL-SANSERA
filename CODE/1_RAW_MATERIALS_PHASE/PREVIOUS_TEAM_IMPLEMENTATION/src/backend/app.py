from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import pandas as pd
import xgboost as xgb
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Get the current script's directory
base_dir = os.path.dirname(os.path.abspath(__file__))

# Load the XGBoost model using joblib (since it's saved as .pkl)
xgboost_model = joblib.load(os.path.join(base_dir, 'xgboost_model.pkl'))

# Load the Random Forest model and label encoders with joblib
random_forest_model = joblib.load(os.path.join(base_dir, 'random_forest_model.pkl'))
label_encoders = joblib.load(os.path.join(base_dir, 'label_encoders.pkl'))


@app.route('/predict_rm', methods=['POST'])
def predict_rm():
    try:
        # Log that a POST request was received
        print("Received a request for XGBoost model prediction")

        # Get the JSON data from the request
        data = request.json
        print("Input data received for XGBoost model:", data)

        # Map the incoming fields to the feature names expected by the model
        input_data = {
            'T/WT_P': float(data['thickness']) if data['thickness'] else 0.0,
            'W/D_P': float(data['width']) if data['width'] else 0.0,
            'L/GF_P': float(data['length']) if data['length'] else 0.0,
        }

        # Initialize the form columns with zeros (binary encoding for form)
        form_columns = {
            'Form_Bar': 0,
            'Form_ROD': 0,
            'Form_Round': 0,
            'Form_Sheet': 0,
            'Form_Flat': 0,
            'Form_Plate': 0,
            'Form_BOP': 0,
            'Form_EXT': 0,
            'Form_CAST': 0
        }

        # Map the incoming 'form' field to the corresponding binary columns
        if data['form'] == 'Bar':
            form_columns['Form_Bar'] = 1
        elif data['form'] == 'Round':
            form_columns['Form_Round'] = 1
        elif data['form'] == 'Flat':
            form_columns['Form_Flat'] = 1
        elif data['form'] == 'EXT':
            form_columns['Form_EXT'] = 1
        elif data['form'] == 'Plate':
            form_columns['Form_Plate'] = 1
        elif data['form'] == 'Sheet':
            form_columns['Form_Sheet'] = 1

        # Combine the input_data (thickness, width, length) and form_columns
        input_data.update(form_columns)

        # Convert the input_data into a DataFrame
        input_df = pd.DataFrame([input_data])

        # Ensure the columns are in the same order as the model's expected features
        expected_features = [
            'T/WT_P', 'W/D_P', 'L/GF_P', 'Form_BOP', 'Form_Bar', 'Form_CAST', 
            'Form_EXT', 'Form_Flat', 'Form_Plate', 'Form_ROD', 'Form_Round', 'Form_Sheet'
        ]
        input_df = input_df[expected_features]

        # Make prediction using the XGBoost model
        #prediction = xgboost_model.predict(input_df)
        prediction = xgboost_model.predict(xgb.DMatrix(input_df))

        print("Part to RM Model prediction:", prediction)

        # Cast the prediction to standard Python float types
        rm_thickness, rm_width, rm_length = map(float, prediction[0])

        # Return the predicted dimensions as JSON
        return jsonify({
            "predicted_dimensions": {
                "rmThickness": rm_thickness,
                "rmWidth": rm_width,
                "rmLength": rm_length
            }
        })

    except Exception as e:
        print("Error during Part to RM prediction:", e)
        return jsonify({"error": "Part to RM Prediction failed"}), 500

# Input Page API (Random Forest model)
@app.route('/predict_price', methods=['POST'])
def predict_price():
    try:
        # Log that a POST request was received
        print("Received a request for Random Forest model prediction")

        # Get the JSON data from the request
        data = request.json
        print("Input data received for Random Forest model:", data)

        # Prepare input data for Random Forest model prediction
        input_data = {
            'Matl. Code': data['material'],
            'Alloy': data['alloy'],
            'Temp': data['temper'],
            'Spec': data['spec'],  # 'spec' is optional
            'Form': data['form'],
            'Weight': float(data['weight']) if data['weight'] else 0.0,
            'Quantity': int(data['quantity']) if data['quantity'] else 0
        }

        # Convert the input_data into a DataFrame
        input_df = pd.DataFrame([input_data])

        # Ensure the columns are in the same order as the model's expected features
        expected_features = ['Matl. Code', 'Alloy', 'Temp', 'Spec', 'Form', 'Weight', 'Quantity']
        input_df = input_df[expected_features]

        categorical_cols = ['Matl. Code', 'Alloy', 'Temp', 'Spec', 'Form']
        for col in categorical_cols:
            input_df[col] = label_encoders[col].transform(input_df[col])
  
        # Make price prediction using the Random Forest model
        predicted_price = random_forest_model.predict(input_df)
        print("Random Forest Model predicted price:", predicted_price)

        # Cast the predicted price to a standard float
        predicted_price = float(predicted_price[0])

        # Generate price predictions for varying quantities
        quantity = int(data['quantity'])
        quantity_range = range(max(0, quantity - 10), min(quantity + 11, 1000))  # 1000 is the upper limit of the quantity
        prices_by_quantity = []
        for current_quantity in quantity_range:
            updated_data = input_data.copy()
            updated_data['Quantity'] = current_quantity
            input_df = pd.DataFrame([updated_data])
            input_df[categorical_cols] = input_df[categorical_cols].apply(lambda x: label_encoders[x.name].transform(x))
            predicted_price = random_forest_model.predict(input_df)[0]
            prices_by_quantity.append(predicted_price)

        # Return the predicted price and prices for varying quantities as JSON
        return jsonify({
            "predicted_price": predicted_price,
            "prices_by_quantity": prices_by_quantity,
            "quantity_range": list(quantity_range)
        })
    
    except Exception as e:
        print("Error during Random Forest prediction:", e)
        return jsonify({"error": "Random Forest Prediction failed"}), 500
    
if __name__ == '__main__':
    app.run(debug=True)




