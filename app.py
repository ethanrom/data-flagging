import streamlit as st
import pandas as pd
import base64

def calculate_allocations(shortages_df, excesses_df):
    shortages_df = shortages_df.sort_values(by='Supply new needed', ascending=False)
    excesses_df = excesses_df[excesses_df['Location Type'] == 'MAIN']
    excesses_df['Excess-Usage Index'] = excesses_df.apply(lambda row: row['EXCESS'] * (1/row['Avg Usage + Usage via dependents']) if row['Avg Usage + Usage via dependents'] != 0 else row['EXCESS'], axis=1)
    excesses_df = excesses_df.sort_values(by='Excess-Usage Index', ascending=False)
    shortages_df['Rolling Stock'] = shortages_df.groupby('Client Warehouse code')['Supply new needed'].transform('sum')
    shortages_df['Rolling Shortage'] = shortages_df['Supply new needed']
    allocations = []
    for _, shortage_row in shortages_df.iterrows():
        part_id = shortage_row['Client Warehouse code']
        shortage = shortage_row['Rolling Shortage']        
        for _, excess_row in excesses_df.iterrows():
            if excess_row['EXCESS'] >= shortage:
                excesses_df.at[excess_row.name, 'EXCESS'] -= shortage
                excesses_df.at[excess_row.name, 'Excess-Usage Index'] = excesses_df.at[excess_row.name, 'EXCESS'] * \
                    (1/excesses_df.at[excess_row.name, 'Avg Usage + Usage via dependents']) if excesses_df.at[excess_row.name, 'Avg Usage + Usage via dependents'] != 0 else \
                    excesses_df.at[excess_row.name, 'EXCESS']
                allocations.append({
                    'From': excess_row['Client Warehouse code'],
                    'To': shortage_row['Client Warehouse code'],
                    'Part ID': part_id,
                    'Quantity': shortage
                })
                shortage = 0
                break
            else:
                excesses_df.at[excess_row.name, 'Excess-Usage Index'] = excesses_df.at[excess_row.name, 'EXCESS'] * \
                    (1/excesses_df.at[excess_row.name, 'Avg Usage + Usage via dependents']) if excesses_df.at[excess_row.name, 'Avg Usage + Usage via dependents'] != 0 else \
                    excesses_df.at[excess_row.name, 'EXCESS']
                short_fulfilled = excesses_df.at[excess_row.name, 'EXCESS']
                shortage -= short_fulfilled
                allocations.append({
                    'From': excess_row['Client Warehouse code'],
                    'To': shortage_row['Client Warehouse code'],
                    'Part ID': part_id,
                    'Quantity': short_fulfilled
                })
                excesses_df.at[excess_row.name, 'EXCESS'] = 0
        shortages_df.at[shortage_row.name, 'Rolling Shortage'] = shortage

    excesses_df['Excess-Usage Index'] = excesses_df.apply(lambda row: row['EXCESS'] * (1/row['Avg Usage + Usage via dependents']) if row['Avg Usage + Usage via dependents'] != 0 else row['EXCESS'], axis=1)
    unfulfilled_shortages = shortages_df[shortages_df['Rolling Shortage'] > 0]
    return allocations, unfulfilled_shortages

def main():
    st.title("Allocation App")
    option = st.sidebar.selectbox("Choose an option:", ("Load Example File", "Upload New File"))

    if option == "Load Example File":
        file_path = "sample.xlsx"
    else:
        uploaded_file = st.sidebar.file_uploader("Upload an Excel file", type=["xlsx"])
        if uploaded_file is not None:
            try:
                with st.spinner('Processing the uploaded file...'):
                    with open("temp.xlsx", "wb") as f:
                        f.write(uploaded_file.getvalue())

                    file_path = "temp.xlsx"
            except Exception as e:
                st.error("Error: Unable to process the uploaded file.")
                st.error(str(e))
                return
        else:
            st.info("Please upload an Excel file.")
            return

    try:
        with st.spinner('Loading data...'):
            xl = pd.ExcelFile(file_path)
            shortages_df = xl.parse("Shortages")
            excesses_df = xl.parse("Excesses")
            allocations, unfulfilled_shortages = calculate_allocations(shortages_df, excesses_df)

        st.subheader("Allocations")
        allocations_df = pd.DataFrame(allocations)
        st.dataframe(allocations_df)

        st.subheader("Unfulfilled Shortages")
        st.dataframe(unfulfilled_shortages[['Client Warehouse code', 'Rolling Shortage']])

        st.subheader("Transfers Made")
        transfers_df = allocations_df.copy()
        transfers_df['Transfer'] = transfers_df['Part ID'] + ' || ' + transfers_df['From'] + ' --> ' + transfers_df[
            'Part ID'] + ' || ' + transfers_df['To'] + ' x ' + transfers_df['Quantity'].astype(str)
        st.dataframe(transfers_df[['Transfer']])

        st.subheader("Final Rolling Shortage")
        final_shortage_df = unfulfilled_shortages.copy()
        final_shortage_df.rename(columns={'Client Warehouse code': 'Part ID'}, inplace=True)
        st.dataframe(final_shortage_df[['Part ID', 'Rolling Shortage']])

        # Download options
        download_options(allocations_df, "Allocations")
        download_options(unfulfilled_shortages[['Client Warehouse code', 'Rolling Shortage']], "Unfulfilled Shortages")
        download_options(transfers_df[['Transfer']], "Transfers Made")
        download_options(final_shortage_df[['Part ID', 'Rolling Shortage']], "Final Rolling Shortage")

    except Exception as e:
        st.error("Error: Unable to process the file.")
        st.error(str(e))

def download_options(data, name):
    csv = data.to_csv(index=False).encode()
    b64 = base64.b64encode(csv).decode()

    st.markdown(f'<a href="data:file/csv;base64,{b64}" download="{name}.csv">Download {name} as CSV</a>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()
