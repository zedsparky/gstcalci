from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def calculate_gst():
    gst_result = None

    if request.method == 'POST':
        amount = float(request.form['amount'])
        tax_type = request.form['tax_type']

        # Check if CGST/SGST were submitted
        cgst = request.form.get('cgst')
        sgst = request.form.get('sgst')
        is_split = cgst and sgst

        if is_split:
            cgst = float(cgst)
            sgst = float(sgst)
            total_gst_rate = cgst + sgst
        else:
            total_gst_rate = float(request.form['gst_rate'])
            cgst = sgst = total_gst_rate / 2  # Optional: mimic a 50-50 split for display

        if tax_type == 'exclusive':
            gst_amount = (amount * total_gst_rate) / 100
            total = amount + gst_amount
        else:  # inclusive
            gst_amount = (amount * total_gst_rate) / (100 + total_gst_rate)
            total = amount

        gst_result = {
            'amount': round(amount, 2),
            'gst_rate': round(total_gst_rate, 2),
            'gst_amount': round(gst_amount, 2),
            'total': round(total, 2),
            'tax_type': tax_type,
            'cgst': round((gst_amount * cgst) / total_gst_rate, 2),
            'sgst': round((gst_amount * sgst) / total_gst_rate, 2),
            'is_split': is_split
        }

    return render_template('index.html', result=gst_result)

if __name__ == '__main__':
    app.run(debug=True)
